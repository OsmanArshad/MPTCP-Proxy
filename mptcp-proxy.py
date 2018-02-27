# <mptcp-proxy.py>
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

        self.content_length = ''
        self.content_range = ''
        self.final_msg = ''
        self.final_msg2 = ''
        self.msg_list = []

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
        # read in the message the client is sending
        while 1:
            self.client_buffer += self.client.recv(BUFLEN)
            end = self.client_buffer.find('\n')
            if end!=-1:
                break

        # split the received message by spaces and create a list containing
        # the method, path, and protocol of the client's request
        data = (self.client_buffer[:end+1]).split()
        self.client_buffer = self.client_buffer[end+1:]
        return data

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

        if self.method == 'GET':
            # Sending head request to get the content length of the requested site
            self.target.send('%s %s %s\r\n%s'%("HEAD", path, self.protocol, self.client_buffer))
            headReqMsg = self.target.recv(4096)
            
            contentLengthPos = headReqMsg.find('Content-Length: ') + 16
            x = contentLengthPos
            while 1:
                if headReqMsg[x].isspace():
                    break
                else:
                    self.content_length += headReqMsg[x] 
                    x += 1

            # Sending the actual request to the server
            requestHeaders1 = 'Range: bytes=0-600\n' + self.client_buffer
            requestHeaders2 = 'Range: bytes=601-1200\n' + self.client_buffer
            
            self.client_buffer = ''
            self.final_msg = ''

            #self.target.send('%s %s %s\n%s'%(self.method, path, self.protocol, self.client_buffer))
            self.target.send('%s %s %s\n%s'%(self.method, path, self.protocol, requestHeaders1))
            self.target.send('%s %s %s\n%s'%(self.method, path, self.protocol, requestHeaders2))

            self._read_write()

            print '\n\n\nTHIS IS SELFFINALMSG'
            print self.final_msg

            self.client.send(self.final_msg)
    
        #else:
        #    self.target.send('%s %s %s\n'%(self.method, path, self.protocol)+self.client_buffer)
        #    #TO DO: need to send another request to "target2" that GETs a different range of bytes
        #    self.client_buffer = ''
            #start the read/write function
        #    self._read_write()

    # makes a connection the host variable that is passed in
    def _connect_target(self, host): 
        i = host.find(':')
        if i!=-1:
            port = int(host[i+1:])
            host = host[:i]
        else:
            port = 80
        (soc_family, _, _, _, address) = socket.getaddrinfo(host, port)[0]
        self.target = socket.socket(soc_family)
        self.target.connect(address)

        (soc_family, _, _, _, address) = socket.getaddrinfo(host, port)[0]
        self.target2 = socket.socket(soc_family)
        self.target2.connect(address)

    #"revolving door" to re-direct the packets in the right direction
    def _read_write(self):
        time_out_max = self.timeout/3
        socs = [self.client, self.target, self.target2]
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
                        if 'Partial Content' in data:
                            contentRangePos = data.find('Content-Range: bytes ') + 21
                            contentRange = ''
                            x = contentRangePos
                            while 1:
                                if data[x] == '/':
                                    break
                                else:
                                    contentRange += data[x] 
                                    x += 1
                            
                            # This is to format HTTP headers for the first partial GET request
                            # The data associated with the request may possibly come thru here
                            if contentRange[0] == '0':
                                splitData = data.splitlines()
                                lastHeaderPos = splitData.index('') + 1

                                httpHeaders = splitData[:lastHeaderPos]
                                attachedData = '\n'.join(splitData[lastHeaderPos:])

                                # Change HTTP message to 200 OK from 206 Partial Content
                                httpMsgTypePos = httpHeaders[0].find('206')
                                httpOkMsg = httpHeaders[0][0:httpMsgTypePos] + '200 OK'
                                httpHeaders[0] = httpOkMsg

                                # Replace Content Length value from a partial to full length
                                contLenHeaderSearch = [i for i, s in enumerate(httpHeaders) if 'Content-Length:' in s]
                                contLenHeaderPos = contLenHeaderSearch[0]
                                httpHeaders[contLenHeaderPos] = 'Content-Length: ' + self.content_length

                                # Delete Content Range header
                                contRngHeaderSearch = [i for i, s in enumerate(httpHeaders) if 'Content-Range:' in s]
                                contRngHeaderPos = contRngHeaderSearch[0]
                                del httpHeaders[contRngHeaderPos]

                                httpHeadersFixed = '\n'.join(httpHeaders)

                                self.final_msg += httpHeadersFixed
                                self.final_msg += '\n'
                                self.final_msg += attachedData

                            # Headers for 2nd partial GET request are removed from data here
                            else:
                                splitData2 = data.splitlines()
                                lastHeaderPos2 = splitData2.index('') + 1
                                attachedData2 = '\n'.join(splitData2[lastHeaderPos2:])

                                self.final_msg += attachedData2

                        # Received data comes here when there are no HTTP headers associated
                        else:
                            self.final_msg += data
                        
                        count = 0
            if count == time_out_max:
                break

#start the proxy server and listen for connections on port 8080
def start_server(host='localhost', port=8080, IPv6=False, timeout=60, handler=ConnectionHandler):
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
