import os
import sys
import http.server as BaseHTTPServer
import socketserver as SocketServer
import urllib.parse as urlparse
import socket
import select
import ssl
import re
import time
import http.client
try:
    import spdylay
except:
    sys.exit('spdyproxy needs spdylay library - http://tatsuhiro-t.github.io/spdylay/')
from SpdyConnection import SpdyConnection
from db import Cache
from db import RttMeasure
from db import MethodGuesser

STATUS_LINE = "HTTP.{4}\s\d{3}\s(.*?)\\\\r\\\\n\\\\r\\\\n"
STATUS_LINE = "HTTP.{4}\s\d{3}\s(.*?)\\r\\n\\r\\n"
BYTES = "b'(.*)'$"
SEPARATOR = "\\r\\n\\r\\n"
SEPARATOR = "\r\n\r\n"

#prints color text
def colorPrint(text,color):
    colors = {}
    colors['Red'] = '\033[91m'
    colors['Green'] = '\033[92m'
    colors['Blue'] = '\033[94m'
    colors['Cyan'] = '\033[96m'
    colors['White'] = '\033[97m'
    colors['Yellow'] = '\033[93m'
    colors['Magenta'] = '\033[95m'
    colors['Grey'] = '\033[90m'
    colors['Black'] = '\033[90m'
    if colors.get(color) is None:
        print(text)
    else:
        print(colors[color]+text+"\033[0m")

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    __base = BaseHTTPServer.BaseHTTPRequestHandler
    __base_handle = __base.handle
    
    def __init__(self, request, client_address, server, cert_file):
        self.cert_file = cert_file
        self.encoding = 'UTF-8'
        self.buf_len = 8192
        self.timeout = 20
        self.rttMeasure = RttMeasure()
        self.Cache = Cache(20)
        self.methodGuesser = MethodGuesser()
        self.__base.__init__(self, request, client_address, server)

    def handle(self):
        (ip, port) =  self.client_address
        colorPrint('Request from '+str(ip)+':'+str(port),'Magenta')
        self.__base_handle()

    def do_GET(self):
        #parse url
        (scm, netloc, path, params, query, fragment) = urlparse.urlparse(self.path, 'http')
        #checking cache
        resource = self.Cache.searchResource(netloc,path)
        if resource:
            self.returnFromCache(resource)
        else:
            self.read_write('http')

    do_HEAD = do_GET
    do_POST = do_GET

    def do_CONNECT(self):
        self.wfile.write(bytes(self.protocol_version+" 200 Connection established\r\n",self.encoding))
        self.wfile.write(bytes("Proxy-agent: %s\r\n" % self.version_string(),self.encoding))
        self.wfile.write(bytes("\r\n",self.encoding))
        try:
            self.connection = ssl.SSLSocket(self.connection, server_side=True, certfile=self.cert_file)
        except ssl.SSLError as e:
            print(e)
        print(self.path.split(':')[0])
        methods = self.methodGuesser.getMethod(self.path.split(':')[0])
        if methods != None:
            if methods['spdy']:
                self.read_write('spdy')
            else:
                self.read_write('https')
        else:
            self.read_write('https')
        return

    def connect_ssl_to(self,netloc):
        soc = self.connect_to(netloc)
        return ssl.SSLSocket(soc)

    def connect_to(self,netloc):
        #default port
        port = 80
        print(netloc)
        tmp = netloc.split(':')
        host = tmp[0]
        if len(tmp)>1:
            colorPrint(tmp[1],'Cyan')
            port = int(tmp[1])
        #create socket
        soc = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            soc.connect((host,port))
            return soc
        except socket.error as arg:
            return 0

    #statistics and caching
    def analyzeResource(self,host,path,header,body=None,time=0,method=None):
        size = 0
        if body != None:
            size = len(body)
        self.Cache.insertResource(host,path,header,body,time,method,size)

    #return resource from cache
    def returnFromCache(self,resource):
        self.connection.send(bytes('HTTP/1.1 200 OK\r\n',self.encoding))
        self.connection.send(bytes(resource['header'],self.encoding))
        self.connection.send(resource['body'])

    def formatHeaders(self,headers):
        final_header = ''
        for header in headers:
            final_header += header[0]+': '+header[1]+'\r\n'
        return final_header

    def getInitialTime(self):
        return float(time.time())

    def getResponseTime(self,initialTime):
        return int((float(time.time()) - initialTime) * 1000)

    def doHTTP(self):
        (scm, netloc, path, params, query, fragment) = urlparse.urlparse(self.path, 'http')
        conn = http.client.HTTPConnection(netloc,80)
        del self.headers['Proxy-Connection']
        initialTime = self.getInitialTime()
        conn.request(self.command,urlparse.urlunparse(('', '', path,params,query,'')),params,self.headers) #method, path, params, headers
        totalTime = self.getResponseTime(initialTime)
        response = conn.getresponse()
        body = response.read()
        final_header = self.formatHeaders(response.getheaders())
        final_header += 'Connection: close\r\n\r\n'
        final_header = final_header.replace('Transfer-Encoding: chunked\r\n','')
        status = 'HTTP/1.'+str(response.version-10)+' '+str(response.status)+' '+response.reason+'\r\n'
        self.connection.send(bytes(status,self.encoding)+bytes(final_header,self.encoding)+body)
        conn.close()
        #to cache
        self.analyzeResource(netloc,path,final_header,body,totalTime,'http')

    def doHTTPS(self,serverConnection,host,method,path,headers):
        initialTime = self.getInitialTime()
        serverConnection.request(method,path)
        totalTime = self.getResponseTime(initialTime)
        response = serverConnection.getresponse()
        body = response.read()
        final_header = self.formatHeaders(response.getheaders())
        final_header = final_header.replace('Transfer-Encoding: chunked','Content-Length: '+str(len(body)))
        final_header += '\r\n'
        status = 'HTTP/1.'+str(response.version-10)+' '+str(response.status)+' '+response.reason+'\r\n'
        self.connection.send(bytes(status,self.encoding)+bytes(final_header,self.encoding)+body)
        #to cache
        self.analyzeResource(host,path,final_header,body,totalTime,'https')

    def doSPDY(self,serverConnection,host,method,path,headers):
        initialTime = self.getInitialTime()
        response = serverConnection.petition(method,path)
        totalTime = self.getResponseTime(initialTime)
        if response['headers'] != None:
            response['headers'] += 'Content-Length:'+str(len(response['data']))+'\r\n\r\n\r\n'
            self.connection.send(bytes(response['headers'],self.encoding)+response['data'])
            #to cache
            self.analyzeResource(host,path,response['headers'],response['data'],totalTime,'spdy')
        else:
            colorPrint('spdy response error','Blue')
            #fallback to https?

    def getConnection(self,protocol,host):
        if protocol == 'https':
            return http.client.HTTPSConnection(host,443)
        if protocol == 'spdy':
            return SpdyConnection((host,443))

    def read_write(self,protocol):
        colorPrint('Protocol: '+protocol,'Yellow')
        (scm, netloc, path, params, query, fragment) = urlparse.urlparse(self.path)
        if netloc != '':
            host = netloc.split(':')[0]
        else:
            host = self.path.split(':')[0]
        #in http the request is previous (method do_GET)
        if protocol == 'http':
            self.doHTTP()
        else:
            count = 0
            total_data = ''
            #make connection according to the method
            serverConnection = self.getConnection(protocol,host)
            while 1:
                count += 1
                try:
                    #receive data from the client (only: client <--https--> proxy)
                    data = self.connection.recv(self.buf_len)
                    if data:
                        total_data += data.decode(self.encoding,'ignore')
                        #if the petition is complete
                        if total_data.find("\r\n\r\n") != -1:
                            colorPrint(total_data,'Red')
                            (method, path, version) = total_data.split('\r\n')[0].split(' ')
                            if method != 'GET':
                                #TODO: send post
                                #headers = re.findall(r"(?P<name>.*?): (?P<value>.*?)\r\n", total_data)
                                #print(headers)
                                #serverConnection.request(method, path, total_data.split('\r\n\r\n')[1]) #headers
                                pass
                            else:
                                #checking cache
                                resource = self.Cache.searchResource(host,path)
                                if resource:
                                    self.returnFromCache(resource)
                                else:
                                    #parse headers:
                                    headers = re.findall(r"(?P<name>.*?): (?P<value>.*?)\r\n", total_data)
                                    if protocol == 'https':
                                        self.doHTTPS(serverConnection,host,method,path,headers)
                                    else:
                                        self.doSPDY(serverConnection,host,method,path,headers)
                            count = 0
                            total_data = ''
                except Exception as e:
                    print(e)
                if count == self.timeout:
                    serverConnection.close()
                    break

class ThreadingHTTPServer(SocketServer.ThreadingMixIn,BaseHTTPServer.HTTPServer):

    #initialize the server with the certificate
    def __init__(self,server_address, RequestHandlerClass, cert_file):
        self.cert_file = cert_file
        BaseHTTPServer.HTTPServer.__init__(self,server_address, RequestHandlerClass);

    #instance request handler with certificate
    def finish_request(self, request, client_address):
        self.RequestHandlerClass(request, client_address, self, self.cert_file)

if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit('Usage: %s <address> <port> <certfile>' % os.path.basename(__file__))
    try:
        httpd = ThreadingHTTPServer((sys.argv[1], int(sys.argv[2])), RequestHandler, sys.argv[3])
        colorPrint('Proxy listening on '+sys.argv[1]+':'+sys.argv[2],'White')
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Ctrl C - Stopping Proxy")
        sys.exit(1)