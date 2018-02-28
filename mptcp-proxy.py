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
        self.final_msg = ''
        self.final_msg_list = []
        self.final_msg_list_temp = []
        self.final_msg_complete = False

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
        self.client.send(HTTPVER+' 200 Connection established\n'+'Proxy-agent: %s\n\n'%VERSION)
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
            n = ""
            while 1:
                if headReqMsg[x].isspace():
                    break
                else:
                    self.content_length += headReqMsg[x] 
                    x += 1

            # Creating the ranges for the two partial GET request
            dataHalf = int(self.content_length) / 2
            firstRange  = str(dataHalf)
            secondRange = str(dataHalf+1)

            requestHeaders1 = 'Range: bytes=0-' + firstRange + '\n' + self.client_buffer
            requestHeaders2 = 'Range: bytes='+ secondRange + '-' + self.content_length + '\n' + self.client_buffer

            self.target.send('%s %s %s\n%s'%(self.method, path, self.protocol, requestHeaders1))
            self.target2.send('%s %s %s\n%s'%(self.method, path, self.protocol, requestHeaders2))

            self.client_buffer = ''
            self.final_msg = ''

            self._read_write()

            print 'Number of times the data came with the headers'
            print self.bungabunga

            self.content_length = ''
            self.final_msg = ''
            self.final_msg_list = []
            self.final_msg_list_temp = []
            self.final_msg_complete = False
    
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
        # self.target.bind(ethernet IP, 0)
        self.target.connect(address)

        (soc_family, _, _, _, address) = socket.getaddrinfo(host, port)[0]
        self.target2 = socket.socket(soc_family)
        # self.target2.bind(ethernet IP, 0)
        self.target2.connect(address)

    #"revolving door" to re-direct the packets in the right direction
    def _read_write(self):
        time_out_max = self.timeout/3
        socs = [self.client, self.target, self.target2]
        count = 0
        self.bungabunga = 0
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
                        print '--------- RECEIVED DATA STARTS HERE ---------'
                        print data
                        print '--------- RECEIVED DATA ENDS HERE ---------'
                        if 'Partial Content' in data:
                            self.bungabunga += 1
                            contentRangePos = data.find('Content-Range: bytes ') + 21
                            contentRange = ''
                            x = contentRangePos
                            while 1:
                                if data[x] == '/':
                                    break
                                else:
                                    contentRange += data[x] 
                                    x += 1
                            
                            print '--------- CONTENT RANGE STARTS HERE ---------'
                            print contentRange
                            
                            # This is to format HTTP headers from the first partial GET request
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

                                httpHeadersFixed = '\n'.join(httpHeaders) + '\n'

                                self.final_msg_list.append(httpHeadersFixed)

                                if len(attachedData) > 15:
                                    self.final_msg_list.append(attachedData)

                            # Headers for 2nd partial GET request are removed from data here
                            else:
                                splitData2 = data.splitlines()
                                lastHeaderPos2 = splitData2.index('') + 1
                                attachedData2 = '\n'.join(splitData2[lastHeaderPos2:])

                                if len(self.final_msg_list) == 2:
                                    if len(attachedData2) > 15:
                                        self.final_msg_list.append(attachedData2)
                                        self.final_msg_complete = True
                                else:
                                    self.final_msg_list_temp.append(attachedData2)

                        # Received data comes here when there are no HTTP headers associated
                        else:
                            if len(self.final_msg_list) == 2:
                                self.final_msg_list.append(data)
                                self.final_msg_complete = True

                            if len(self.final_msg_list) == 1:
                                self.final_msg_list.append(data)

                        if self.final_msg_complete:
                            for msg in self.final_msg_list:
                                self.final_msg += msg
                            self.client.send(self.final_msg)

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
