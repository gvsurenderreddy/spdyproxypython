import os
import sys
import http.server as BaseHTTPServer
import socketserver as SocketServer
import urllib.parse as urlparse
import socket
import select
import ssl
import re
try:
    import spdylay
except:
    sys.exit('spdyproxy needs spdylay library - http://tatsuhiro-t.github.io/spdylay/')
    #TODO: fallback https without spdy

#---------SPDY---------

class MyStreamHandler(spdylay.BaseSPDYStreamHandler):
    def __init__(self, url, fetcher, soc):
        self.soc = soc #client socket
        spdylay.BaseSPDYStreamHandler.__init__(self, url, fetcher)

    def on_header(self, nv):
        sys.stdout.write('Stream#{}\n'.format(self.stream_id))
        for k, v in nv:
            sys.stdout.write('{}: {}\n'.format(k, v))

    def on_data(self, data):
        sys.stdout.write('Stream#{}\n'.format(self.stream_id))
        #sys.stdout.buffer.write(data)

    def on_close(self, status_code):
        sys.stdout.write('Stream#{} closed\n'.format(self.stream_id))

class MyUrlFetcher(spdylay.UrlFetcher):
    def __init__(self, server_address, urls, StreamHandlerClass, soc):
        print(soc)
        self.server_address = server_address
        self.handlers = [StreamHandlerClass(url, self, soc) for url in urls] #this is the changed line
        self.streams = {}
        self.finished = []

        self.ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.ctx.options = ssl.OP_ALL | ssl.OP_NO_SSLv2 | \
        ssl.OP_NO_COMPRESSION
        self.ctx.set_npn_protocols(spdylay.get_npn_protocols())

def urlfetch(urls, StreamHandlerClass, soc):
    res = spdylay.urlsplit(urls[0])
    if res.scheme != 'https':
        raise spdylay.UrlFetchError('Unsupported scheme {}'.format(res.scheme))
    hostname = res.hostname
    port = res.port if res.port else 443

    f = MyUrlFetcher((hostname, port), urls, StreamHandlerClass, soc)
    f.loop()

#---------SPDY---------

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
    buf_len = 8192

    #only to give it the certificate
    def __init__(self, request, client_address, server, cert_file):
        self.cert_file = cert_file
        self.encoding = 'UTF-8'
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
            self.read_write(soc)
            return
        else:
            self.send_error(404, 'Could not connect socket')

    do_HEAD = do_GET
    do_POST = do_GET

    def do_CONNECT(self):
        soc = self.connect_ssl_to(self.path)
        if soc:
            self.wfile.write(bytes(self.protocol_version+" 200 Connection established\r\n",self.encoding))
            self.wfile.write(bytes("Proxy-agent: %s\r\n" % self.version_string(),self.encoding))
            self.wfile.write(bytes("\r\n",self.encoding))

            try:
                self.connection = ssl.SSLSocket(self.connection, server_side=True, certfile=self.cert_file)
            except ssl.SSLError as e:
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
                        #from the client (only ssl)
                        out = soc

                        #try:
                        #    urlfetch(uris, MyStreamHandler, 'PERROS')
                        #    print('castor')
                        #except spdylay.UrlFetchError as error:
                        #    print (error)

                        if data:
                            #parse headers:
                            #print(re.findall(r"(?P<name>.*?): (?P<value>.*?)\r\n", data))
                            #data = data.replace('Accept-Encoding: gzip, deflate\r\n','')
                            colorPrint(data.decode(self.encoding),'Green')
                    else:
                        #from the web server
                        out = self.connection
                    if data:
                        #total_data += data #doesnt work in python 3.3
                        out.send(data)
                        count = 0
                #colorPrint(total_data,'Magenta')
            if count == 60:
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