import os
import sys
import BaseHTTPServer
import SocketServer
import urlparse
import socket
import select
import ssl
import re

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
        print text
    else:
        print colors[color]+text+"\033[0m"

class RequestHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    __base = BaseHTTPServer.BaseHTTPRequestHandler
    __base_handle = __base.handle
    buf_len = 8192
    pem_file = 'mycert.pem'

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
            soc.send("%s %s %s\r\n" % (self.command,urlparse.urlunparse(('', '', path,params, query,'')),self.request_version))
            self.headers['Connection'] = 'close'
            del self.headers['Proxy-Connection']
            for key_val in self.headers.items():
                soc.send("%s: %s\r\n" % key_val)
            soc.send("\r\n")
            self.read_write(soc)
            return
        else:
            self.send_error(404, 'Could not connect socket')

    do_HEAD = do_GET
    do_POST = do_GET

    def do_CONNECT(self):
        soc = self.connect_ssl_to(self.path)
        if soc:
            self.wfile.write(self.protocol_version+" 200 Connection established\r\n")
            self.wfile.write("Proxy-agent: %s\r\n" % self.version_string())
            self.wfile.write("\r\n")

            try:
                self.connection = ssl.SSLSocket(self.connection, server_side=True, certfile=self.pem_file)
            except ssl.SSLError, e:
                logging.error(e)

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
        print netloc
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
        except socket.error, arg:
            return 0

    def read_write(self,soc):
        socs = [self.connection, soc]
        count = 0
        while 1:
            count += 1
            (recv, _, error) = select.select(socs, [], socs, 3)
            if error:
                break
            if recv:
                total_data = ''
                for in_ in recv:
                    try:
                        data = in_.recv(self.buf_len)
                    except:
                        data = 0
                    if in_ is self.connection:
                        colorPrint('FROM CLIENT','Yellow')
                        out = soc
                        #if data:
                            #parse headers:
                            #print re.findall(r"(?P<name>.*?): (?P<value>.*?)\r\n", data)
                            #data = data.replace('Accept-Encoding: gzip, deflate\r\n','')
                            #colorPrint(data,'Green')
                    else:
                        colorPrint('FROM WEB SERVER','Yellow')
                        out = self.connection
                    if data:
                        total_data += data
                        out.send(data)
                        count = 0
                #colorPrint(total_data,'Magenta')
            if count == 60:
                break

class ThreadingHTTPServer(SocketServer.ThreadingMixIn,BaseHTTPServer.HTTPServer):
    pass

if __name__ == "__main__":
    try:
        httpd = ThreadingHTTPServer(('localhost', 8080), RequestHandler)
        colorPrint('Proxy on localhost:8080','White')
        httpd.serve_forever()
    except KeyboardInterrupt:
        print "Ctrl C - Stopping Proxy"
        sys.exit(1)