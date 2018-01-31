# -*- coding: cp1252 -*-
# <PythonProxy.py>
# curl -x localhost:8080 http://www.cs.ucr.edu/~eamonn/cs170/
import socket, thread, select, httplib

__version__ = '0.1.0 Draft 1'
BUFLEN = 8192
VERSION = 'Python Proxy/'+__version__
HTTPVER = 'HTTP/1.1'

class ConnectionHandler:
    def __init__(self, connection, address, timeout):
        self.client = connection
        self.client_buffer = ''
        self.timeout = timeout
        
        #print the request and it extracts the protocol and path
        self.method, self.path, self.protocol = self.get_base_header()
        
        if self.method=='CONNECT':
            self.method_CONNECT()

        #handle the GET request
        elif self.method in ('OPTIONS', 'GET', 'HEAD', 'POST', 'PUT',
                             'DELETE', 'TRACE'):
            self.method_others()

        self.client.close()
        self.target.close()

    def get_base_header(self):
        while 1:
            self.client_buffer += self.client.recv(BUFLEN)  # receives data from client continuously
            end = self.client_buffer.find('\n')             # when you reach new line symbol, stop reading input
            if end!=-1:
                break

        #print the request
        print '%s'%self.client_buffer[:end]#debug

        data = (self.client_buffer[:end+1]).split()         # split the received message by spaces and store as a list into data variable
        self.client_buffer = self.client_buffer[end+1:]
        return data                                         # data variable is a python list that also holds method, path, protocol

    def method_CONNECT(self):
        print('connect!')
        self._connect_target(self.path)
        self.client.send(HTTPVER+' 200 Connection established\n'+
                         'Proxy-agent: %s\n\n'%VERSION)
        self.client_buffer = ''
        self._read_write()        

    #forward the packet to its final destination
    def method_others(self):
        self.path = self.path[7:]
        i = self.path.find('/')
        host = self.path[:i]        
        path = self.path[i:]
        self._connect_target(host)

        #TO DO: first find out the Content-Length by sending a RANGE request
        self.target.send('%s %s %s\r\n%s'%("HEAD", path, self.protocol,
                         self.client_buffer))
        headReqMsg = self.target.recv(4096)
        contentLengthPos = headReqMsg.find('Content-Length: ')

        contentLengthValPos = contentLengthPos + 16
        contentLength = ''
        x = contentLengthValPos
        while 1:
            if headReqMsg[x].isspace():
                break
            else:
                contentLength += headReqMsg[x] 
                x += 1
                
        print contentLength
        #print('%s %s %s\r\n%s'%(self.method, path, self.protocol,
                         #self.client_buffer))
        self.target.send('%s %s %s\r\n%s'%(self.method, path, self.protocol,
                         self.client_buffer))
        #TO DO: need to send another request to "target2" that GETs a different range of bytes
        self.client_buffer = ''

        #start the read/write function
        self._read_write()

    def _connect_target(self, host):        # makes a connection the host variable that is passed in
        i = host.find(':')
        if i!=-1:
            port = int(host[i+1:])
            host = host[:i]
        else:
            port = 80
        (soc_family, _, _, _, address) = socket.getaddrinfo(host, port)[0]
        self.target = socket.socket(soc_family)
        self.target.connect(address)

    #"revolving door" to re-direct the packets in the right direction
    def _read_write(self):
        time_out_max = self.timeout/3
        socs = [self.client, self.target]
        count = 0
        while 1:
            count += 1
            (recv, _, error) = select.select(socs, [], socs, 3)
            if error:
                break
            if recv:
                for in_ in recv:
                    data = in_.recv(BUFLEN)
                    if in_ is self.client:
                        out = self.target
                    else:
                        out = self.client
                    if data:
                        #TO DO: Check if it's response to the RANGE request and extract the Content-Length

                        #TO DO: merge the data from both interfaces into one big data, if we are receiving

                        out.send(data)
                        count = 0
            if count == time_out_max:
                break

#start the proxy server and listen for connections on port 8080
def start_server(host='localhost', port=8080, IPv6=False, timeout=60,
                  handler=ConnectionHandler):
    if IPv6==True:
        soc_type=socket.AF_INET6
    else:
        soc_type=socket.AF_INET
    soc = socket.socket(soc_type)
    soc.bind((host, port))
    print "Serving on %s:%d."%(host, port)#debug
    soc.listen(0)
    while 1:
        thread.start_new_thread(handler, soc.accept()+(timeout,))

if __name__ == '__main__':
    start_server()
