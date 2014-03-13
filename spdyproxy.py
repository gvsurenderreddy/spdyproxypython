import os
import sys
import thread
import socket
import ssl
from urlparse import urlparse
import pymongo

class Spdyproxy:
	def __init__(self,port,host='',backlog=50):
		self.port = port
		self.host = host
		self.backlog = backlog
		self.max_data_recv = 999999

	def startProxy(self):
		try:
	        #create, bind and listen
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			s.bind((self.host, self.port))
			s.listen(self.backlog)
			self.colorPrint('Proxy listening on '+self.host+':'+str(self.port),92)
		except socket.error, (value, message):
			if s:
				s.close()
			print "Could not open socket: ", message
			sys.exit(1)

		while 1:
			conn, addr = s.accept()
			thread.start_new_thread(self.handleRequest, (conn, addr))
		s.close()

	def colorPrint(self,text,colorNum):
	    print "\033["+str(colorNum)+"m"+text+"\033[0m"

	def handleRequest(self,conn,addr):
		request = conn.recv(self.max_data_recv)

		#parse url
		try:
			method = request.split(' ')[0]
			url = urlparse(request.split('\n')[0].split(' ')[1])
			self.colorPrint(method+': '+url.geturl(),94)
		except Exception:
			print request
			conn.close()
			sys.exit(1)

		#defaults ports
		port = 80
		if(method=='CONNECT'):
			port = 443
		if url.port:
			port = url.port

		if(method=='CONNECT'):
			self.handleSecure(conn, addr, request, url, port)
		else:
			self.handlePlain(conn, addr, request, url, port)

	def handlePlain(self,conn,addr,request,url,port):
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)  
			#s.connect((url.netloc, port))
			#para usar proxy
			s.connect(('proxy.unlu.edu.ar', 8080))
			s.send(request)
			while 1:
				data = s.recv(self.max_data_recv)
				if (len(data) > 0):
					conn.send(data)
				else:
					break
			s.close()
			conn.close()
		except socket.error, (value, message):
			if s:
				s.close()
			if conn:
				conn.close()
			self.colorPrint("Socket Error: "+message,91)
			sys.exit(1)

	def handleSecure(self,conn,addr,request,url,port):
		#send('HTTP/1.1 200 Connection established\n'+'Proxy-agent: spdyProxy 0.1\n\n')
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			ssl_sock = ssl.wrap_socket(s,ca_certs="ca_certs_file",cert_reqs=ssl.CERT_REQUIRED)
			ssl_sock.connect((url.netloc, port))
			#s.connect(('proxy.unlu.edu.ar', 8080))
			request = request.replace('CONNECT','GET');
			ssl_sock.send(request)
			
			while 1:
				data = ssl_sock.recv(self.max_data_recv)
				if (len(data) > 0):
					conn.send(data)
				else:
					break
			ssl_sock.close()
			conn.close()
		except socket.error, (value, message):
			if s:
				s.close()
			if conn:
				conn.close()
			self.colorPrint("Socket Error: "+message,91)
			sys.exit(1)

if __name__ == '__main__':
	try:
		proxy = Spdyproxy(8080)
		#proxy.startProxy()
		client = pymongo.MongoClient('localhost', 27017)
		db = client.test_database
		#post = {"name": "maxi","text": "My first insert"}
		#db.people.insert(post)
		people = db.people.find()
		print people[0]
	except KeyboardInterrupt:
		print "Ctrl C - Stopping Proxy"
		sys.exit(1)