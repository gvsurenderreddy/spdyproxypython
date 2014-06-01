import ssl
import spdylay
import socket
import socketserver
import select
import sys

class SpdyConnection:
    def __init__(self, server_address):
        self.server_address = server_address
        self.ctx = ssl.SSLContext(ssl.PROTOCOL_SSLv23)
        self.ctx.options = ssl.OP_ALL | ssl.OP_NO_SSLv2 | \
            ssl.OP_NO_COMPRESSION
        self.ctx.set_npn_protocols(spdylay.get_npn_protocols())

        self.streams = {}
        self.finished = []
        self.response = {}
        self.response['headers'] = None
        self.response['data'] = bytes('','UTF-8')

        #connect the socket
        self.connect(self.server_address)
        #create spdy session
        self.create_session()

    def connect(self, server_address):
        self.sock = None
        try:
            for res in socket.getaddrinfo(server_address[0], server_address[1],
                                          socket.AF_UNSPEC,
                                          socket.SOCK_STREAM):
                af, socktype, proto, canonname, sa = res
                try:
                    self.sock = socket.socket(af, socktype, proto)
                    #self.sock.settimeout(2)
                except OSError as msg:
                    self.sock = None
                    continue
                try:
                    self.sock.connect(sa)
                except OSError as msg:
                    self.sock.close()
                    self.sock = None
                    continue
                break
            else:
                raise spdylay.UrlFetchError('Could not connect to {}'\
                                        .format(server_address))
        except socket.gaierror as e:
            raise spdylay.UrlFetchError('Could not connect to {}'\
                                        .format(server_address))

    def tls_handshake(self):
        self.sock = self.ctx.wrap_socket(self.sock, server_side=False,
                                         do_handshake_on_connect=False)
        self.sock.do_handshake()

        self.version = spdylay.npn_get_version(self.sock.selected_npn_protocol())
        if self.version == 0:
            raise spdylay.UrlFetchError('NPN failed')

    def close(self):
        self.sock.shutdown(socket.SHUT_RDWR)
        self.sock.close()

    def create_session(self):
        self.tls_handshake()
        self.sock.setblocking(False)

        self.session = spdylay.Session(spdylay.CLIENT,
                          self.version,
                          send_cb=self.send_cb,
                          on_ctrl_recv_cb=self.on_ctrl_recv_cb,
                          on_data_chunk_recv_cb=self.on_data_chunk_recv_cb,
                          before_ctrl_send_cb=self.before_ctrl_send_cb,
                          on_stream_close_cb=self.on_stream_close_cb)

        self.session.submit_settings(\
            spdylay.FLAG_SETTINGS_NONE,
            [(spdylay.SETTINGS_MAX_CONCURRENT_STREAMS, spdylay.ID_FLAG_SETTINGS_NONE, 100)]
            )

    #returns response with headers and data
    def petition(self,method,path):
        self.finish = 0

        if self.server_address[1] == 443:
            hostport = self.server_address[0]
        else:
            hostport = '{}:{}'.format(self.server_address[0],
                                      self.server_address[1])
        self.session.submit_request(0,
                           [(':method', method),
                            (':scheme', 'https'),
                            (':path', path),
                            (':version', 'HTTP/1.1'),
                            (':host', hostport),
                            ('accept', '*/*'),
                            ('user-agent', 'python-spdylay')],
                           )

        while (self.session.want_read() or self.session.want_write()) \
                and not self.finish:
            want_read = want_write = False
            try:
                data = self.sock.recv(8192)
                if data:
                    self.session.recv(data)
                else:
                    break
            except ssl.SSLWantReadError:
                want_read = True
            except ssl.SSLWantWriteError:
                want_write = True
            try:
                self.session.send()
            except ssl.SSLWantReadError:
                want_read = True
            except ssl.SSLWantWriteError:
                want_write = True

            if want_read or want_write:
                select.select([self.sock] if want_read else [],
                              [self.sock] if want_write else [],
                              [])
        return self.response

    def send_cb(self, session, data):
        return self.sock.send(data)

    def before_ctrl_send_cb(self, session, frame):
        pass
        #if frame.frame_type == spdylay.SYN_STREAM:
            #print(frame.stream_id)

    def format_headers(self,headers):
        #protocol status
        #headers_field: header_value
        header = ''
        header += next(filter(lambda x:x[0]==':version',headers))[1]+' '
        header += next(filter(lambda x:x[0]==':status',headers))[1]+'\r\n'
        for x in headers:
            if x[0] != ':version' and x[0] != ':status':
                header += x[0]+': '+x[1]+'\r\n'
        #header += 'Transfer-Encoding: gzip\r\n'
        return header

    def on_ctrl_recv_cb(self, session, frame):
        if frame.frame_type == spdylay.SYN_REPLY or frame.frame_type == spdylay.HEADERS:
            self.response['headers'] = self.format_headers(frame.nv)

    def on_data_chunk_recv_cb(self, session, flags, stream_id, data):
        self.response['data'] += data

    def on_stream_close_cb(self, session, stream_id, status_code):
        #print('Stream close '+str(status_code))
        self.finish = 1

#EXAMPLE
#if __name__ == "__main__":
#    try:
#        spdyClient = SPDYConnection(('www.google.com',443))
#        response = spdyClient.petition('GET','/')
#        print(response)
#        response = spdyClient.petition('GET','/images/srpr/logo11w.png')
#        print(response)
#        spdyClient.close()
#    except spdylay.UrlFetchError as error:
#        print (error)