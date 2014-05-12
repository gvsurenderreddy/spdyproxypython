import os
import sys
import http.server as BaseHTTPServer
import socketserver as SocketServer
import urllib.parse as urlparse
import socket
import select
import ssl
import re
from SpdyConnection import SpdyConnection
#from bitstring import ConstBitStream
try:
    import spdylay
except:
    sys.exit('spdyproxy needs spdylay library - http://tatsuhiro-t.github.io/spdylay/')

STATUS_LINE = "HTTP.{4}\s\d{3}\s(.*?)\\\\r\\\\n\\\\r\\\\n"
BYTES = "b'(.*)'$"
SEPARATOR = "\\r\\n\\r\\n"

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
    
    #only to give it the certificate
    def __init__(self, request, client_address, server, cert_file):
        self.cert_file = cert_file
        self.encoding = 'UTF-8'
        self.buf_len = 8192
        self.timeout = 20
        self.__base.__init__(self, request, client_address, server)

    def handle(self):
        (ip, port) =  self.client_address
        colorPrint('Request from '+str(ip)+':'+str(port),'Magenta')
        self.__base_handle()

    def do_GET(self):
        #parse url
        (scm, netloc, path, params, query, fragment) = urlparse.urlparse(self.path, 'http')
        soc = self.connect_to(netloc)
        if soc:
            #send petition to the web server
            petition = bytes("%s %s %s\r\n" % (self.command,urlparse.urlunparse(('', '', path,params, query,'')),self.request_version),self.encoding)
            soc.send(petition)
            self.headers['Connection'] = 'close'
            del self.headers['Proxy-Connection']
            for key_val in self.headers.items():
                soc.send(bytes("%s: %s\r\n" % key_val,self.encoding))
            soc.send(bytes("\r\n",self.encoding))
            self.read_write(soc,petition)
            return
        else:
            self.send_error(404, 'Could not connect socket')

    do_HEAD = do_GET
    do_POST = do_GET

    def do_CONNECT(self):
        colorPrint(self.path,'Blue')
        try:
            #TODO: save spdy sites. save connection in connection pool
            spdyClient = SpdyConnection((self.path.split(':')[0],443))
            spdyClient.close()
            soc = 'spdy'
            soc = self.connect_ssl_to(self.path)
        except spdylay.UrlFetchError as error:
            soc = self.connect_ssl_to(self.path)

        if soc:
            self.wfile.write(bytes(self.protocol_version+" 200 Connection established\r\n",self.encoding))
            self.wfile.write(bytes("Proxy-agent: %s\r\n" % self.version_string(),self.encoding))
            self.wfile.write(bytes("\r\n",self.encoding))
            try:
                self.connection = ssl.SSLSocket(self.connection, server_side=True, certfile=self.cert_file)
            except ssl.SSLError as e:
                logging.error(e)

            if soc == 'spdy':
                self.read_write_spdy()
            else:
                self.read_write(soc)
            return
        else:
            self.send_error(404, 'Could not connect socket')

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

    def read_write(self,soc,petition=None):
        socs = [self.connection, soc]
        count = 0
        total_response = total_data = ''
        #total_response = bytes('',self.encoding)
        #array with the petitions and the response
        petitions_sent = []
        #request + header + body
        resource = {}
        resource['request'] = ''
        resource['header'] = ''
        resource['body'] = ''
        
        #index of actual response
        actual_response = 0

        #only on GET method
        if petition != None:
            #add the first petition
            petitions_sent.append({'request':petition})
        while 1:
            print(str(count))
            count += 1
            (recv, _, error) = select.select(socs, [], socs, 3)
            if error:
                break
            if recv:
                for in_ in recv:
                    try:
                        data = in_.recv(self.buf_len)
                    except Exception as e:
                        print(e)
                        data = 0
                    if in_ is self.connection:
                        #from the client (only ssl)
                        out = soc
                        #if data:
                        #    out.send(data)
                        #    count = 0
                        if data:
                            total_data += data.decode(self.encoding)
                            if total_data.find('\r\n\r\n') != -1:
                                print(total_data)
                                
                                petitions_sent.append({'resource':total_data})
                                
                                colorPrint('envio peticion','Red')
                                out.send(bytes(total_data,self.encoding))
                                count = 0
                                total_data = ''
                    else:
                        #from the web server
                        out = self.connection
                        if data:
                            try:
                                total_response += str(data)[2:-1] #eliminates 'b ... '
                                result = self.search_header(total_response)
                                if result != 0:
                                    colorPrint('-----------'+str(actual_response),'Blue')
                                    petitions_sent[actual_response]['header'] = total_response[result.start():result.end()]
                                    colorPrint('HEADER :'+str(petitions_sent[actual_response]['header']),'Red')
                                    #the first resource could not be completed
                                    if actual_response != 0:
                                        petitions_sent[actual_response-1]['body'] = total_response[:result.start()]
                                        colorPrint('body added','Blue')
                                        #print(petitions_sent)
                                    total_response = total_response[result.end():]
                                    actual_response += 1
                                else:
                                    pass
                            except Exception as e:
                                print(e)
                                pass
                            #send data to the client
                            out.send(data)
                            count = 0
                        else:
                            print('no hay datos')
                            #print(petitions_sent)
                            #print(total_response)                            
                            if total_response != '':
                                petitions_sent[actual_response-1]['body'] = total_response
                                total_response = ''
                                actual_response += 1
            if count == self.timeout:
                break
        #last body
        if total_response != '':
            petitions_sent[actual_response-1]['body'] = total_response
        colorPrint('FINAL PETITION','Blue')
        print(petitions_sent)
        #sys.stdout.buffer.write(response)
        colorPrint('------------------','Blue')

    #search header and returns start and end of the header
    def search_header(self,var):
        #STATUS_LINE
        result = re.search(STATUS_LINE, var, flags=re.DOTALL)
        if result:
            #print('resultado '+str(result.start())+' - '+str(result.end()))
            #colorPrint(str(var).split(SEPARATOR)[0],'White')
            if var.find(SEPARATOR) != -1:
                #the header is complete
                return result
        return 0

    def read_write_spdy(self):
        count = 0
        total_data = ''
        while 1:
            count += 1
            try:
                data = self.connection.recv(self.buf_len)

                if data:
                    #parse headers:
                    #print(re.findall(r"(?P<name>.*?): (?P<value>.*?)\r\n", data.decode(self.encoding)))
                    #data = data.replace('Accept-Encoding: gzip, deflate\r\n','')
                    total_data += data.decode(self.encoding)
                    #print(data.decode(self.encoding))
                    #if the petition is complete
                    if total_data.find("\r\n\r\n") != -1:
                        #colorPrint(total_data,'Magenta')
                        (method, path, version) = total_data.split('\r\n')[0].split(' ')
                        #host = re.findall(r"Host: (?P<value>.*?)\r\n", total_data)[0]
                        host = self.path.split(':')[0]
                        print(host,path)
                        #spdy connection
                        #TODO: connection pool, reusing the connection
                        try:
                            spdyClient = SpdyConnection((host,443))
                            response = spdyClient.petition(method,path)
                            spdyClient.close()

                            if response['headers'] != None:
                                print(response['headers'])
                                response['headers'] += 'Content-Length:'+str(len(response['data']))+'\r\n\r\n\r\n'
                                print(response['headers'])
                                self.connection.send(bytes(response['headers'],self.encoding)+response['data'])
                                count = 0
                                total_data = ''
                            else:
                                colorPrint('spdy response error','Blue')
                        except spdylay.UrlFetchError as error:
                            #fallback to http/https
                            colorPrint('spdy connection error','Blue')
                            pass
            except Exception as e:
                print(e)
                colorPrint('data receive error','Blue')
                pass
            if count == self.timeout:
                #print('closing connection...')
                #self.connection.close()
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