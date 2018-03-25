# MPTCP proxy server
# Erik Arriaga
# Osman Arshad

import socket, thread, select, time

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

        self.content_size_on_target = 0
        self.content_size_on_target2 = 0

        self.haveTargetHeaders = False
        self.haveTarget2Headers = False

        self.targetFullHeaders = ''
        self.target2FullHeaders = ''

        self.data_recvd_on_target = ''
        self.data_recvd_on_target2 = ''
        
        self.all_target_data_rcvd = False
        self.all_target2_data_rcvd = False

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
        self.target2.close()

    def get_base_header(self):
        while 1:
            self.client_buffer += self.client.recv(BUFLEN)
            end = self.client_buffer.find('\n')
            if end!=-1:
                break

        data = (self.client_buffer[:end+1]).split()
        self.client_buffer = self.client_buffer[end+1:]
        return data

    def method_CONNECT(self):
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
        if self.method == 'GET':
            # Sending head request to get the content length of the requested site

            start = time.time()
            self.target.send('%s %s %s\r\n%s'%("HEAD", path, self.protocol, self.client_buffer))
            
            headReqMsg = ''
            while 1:
                headReqMsg += self.target.recv(4096)
                if (headReqMsg.find('\r\n\r\n')):
                    break
            
            contentLengthPos = headReqMsg.find('Content-Length: ') + 16
            while 1:
                if headReqMsg[contentLengthPos].isspace():
                    break
                else:
                    self.content_length += headReqMsg[contentLengthPos] 
                    contentLengthPos += 1

            print 'The total content length for this data is: ' + str(self.content_length) 
            dataHalf = int(self.content_length) / 2
            firstRange  = str(dataHalf)
            secondRange = str(dataHalf+1)

            requestHeaders1 = 'Range: bytes=0-' + firstRange + '\n' + self.client_buffer
            requestHeaders2 = 'Range: bytes='+ secondRange + '-' + self.content_length + '\n' + self.client_buffer

            self.original_content_length = self.content_length

            adjustedContentLength = int(self.content_length) - 1
            self.content_length = str(adjustedContentLength)

            self.target.send('%s %s %s\n%s'%(self.method, path, self.protocol, requestHeaders1))
            self.target2.send('%s %s %s\n%s'%(self.method, path, self.protocol, requestHeaders2))

            self.client_buffer = ''
            self.final_msg = ''

            #print '\n\n_________________________________START___________________________________________'
            self._read_write()
            end = time.time()
            print 'TIME'
            print end - start

            # Resetting all global variables here
            self.content_length = ''

            self.content_size_on_target = 0
            self.content_size_on_target2 = 0

            self.haveTargetHeaders = False
            self.haveTarget2Headers = False

            self.targetFullHeaders = ''
            self.target2FullHeaders = ''

            self.data_recvd_on_target = ''
            self.data_recvd_on_target2 = ''
            
            self.all_target_data_rcvd = False
            self.all_target2_data_rcvd = False

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
                    if in_ is self.target:
                        currently_using = 'target'
                    if in_ is self.target2:
                        currently_using = 'target2'
                    else:
                        out = self.client
                    if data:
                        #print '--------->>>>>>DATA ARRIVED ON ' + currently_using
                        #print data

                        # Received data comes here when there are no HTTP headers associated
                        if currently_using == 'target' and self.haveTargetHeaders == True:
                            self.data_recvd_on_target += data 
                            #print 'LENGTH OF LATE DATA IS::: ' + str(len(data))
                            #print 'TARGET CONTENT SIZE WANTED IS::::::::: ' + str(self.content_size_on_target)                            
                            if self.content_size_on_target == len(data):
                                self.all_target_data_rcvd = True
                            else:
                                self.content_size_on_target = self.content_size_on_target - len(data)
                        
                        if currently_using == 'target2' and self.haveTarget2Headers == True:
                            self.data_recvd_on_target2 += data
                            #print 'LENGTH OF LATE DATA IS::: ' + str(len(data))
                            #print 'TARGET2 CONTENT SIZE WANTED IS::::::::: ' + str(self.content_size_on_target2)  
                            if self.content_size_on_target2 == len(data):
                                self.all_target2_data_rcvd = True
                            else:
                                self.content_size_on_target2 = self.content_size_on_target2 - len(data)


                        if currently_using == 'target' and self.haveTargetHeaders == False:
                            self.targetFullHeaders += data
                            #print 'DONT HAVE TARGET HEADERS YET'
                            if self.targetFullHeaders.find('\r\n\r\n') != -1:
                                #print 'GOT TARGET HEADERS YET'
                                self.haveTargetHeaders = True

                                # First the content range of this data is extracted from headers
                                contentRangePos = self.targetFullHeaders.find('Content-Range: bytes ') + 21
                                contentRange = ''
                                isStartRange = True
                                isEndRange = False
                                startRange = ''
                                endRange = ''                       

                                while 1:
                                    if self.targetFullHeaders[contentRangePos] == '/':
                                        break
                                    else:
                                        contentRange += self.targetFullHeaders[contentRangePos]
                                        if isStartRange:
                                            startRange += self.targetFullHeaders[contentRangePos]
                                        if isEndRange:
                                            endRange += self.targetFullHeaders[contentRangePos]
                                        if self.targetFullHeaders[contentRangePos] == '-':
                                            isEndRange = True
                                            isStartRange = False
                                        contentRangePos += 1

                                startRange = startRange[:-1]
                                self.content_size_on_target = int(endRange) - int(startRange) + 1

                                dataSplit = self.targetFullHeaders.splitlines()
                                endOfHeadersPos = 0
                                for p in dataSplit:
                                    endOfHeadersPos += len(p) + 2
                                    if p == '':
                                        break        

                                # Determines whether associated data was included        
                                if len(self.targetFullHeaders) != endOfHeadersPos:
                                    dataIncluded = True
                                elif len(self.targetFullHeaders) == endOfHeadersPos:
                                    dataIncluded = False

                                # Extracting the headers from the first request, and reformatting it
                                # into an appropriate response format for the client
                                if startRange == '0':
                                    # Extract the http headers from the data  
                                    finalHeaderPos = dataSplit.index('') + 1

                                    httpHeadersSplit = dataSplit[:finalHeaderPos]              

                                    # Change HTTP message to 200 OK from 206 Partial Content
                                    httpMsgTypePos = httpHeadersSplit[0].find('206')
                                    httpOkMsg = httpHeadersSplit[0][0:httpMsgTypePos] + '200 OK'
                                    httpHeadersSplit[0] = httpOkMsg

                                    # Replace Content Length value from a partial to full length
                                    contLenHeaderSearch = [i for i, s in enumerate(httpHeadersSplit) if 'Content-Length:' in s]
                                    contLenHeaderPos = contLenHeaderSearch[0]
                                    httpHeadersSplit[contLenHeaderPos] = 'Content-Length: ' + self.original_content_length

                                    # Delete Content Range header
                                    contRngHeaderSearch = [i for i, s in enumerate(httpHeadersSplit) if 'Content-Range:' in s]
                                    contRngHeaderPos = contRngHeaderSearch[0]
                                    del httpHeadersSplit[contRngHeaderPos]

                                    httpHeadersFixed = '\n'.join(httpHeadersSplit) + '\n'
                                    self.final_msg = httpHeadersFixed 

                                contentData = ''
                                # Here we extract data that came attached to the headers
                                if dataIncluded:
                                    #print 'SO THE DATA CAME WITH THE HEADERS ON ' + currently_using
                                    contentData = self.targetFullHeaders[endOfHeadersPos:]

                                    self.data_recvd_on_target += contentData
                                    #print 'LENGTH OF DATA ON HEADERS IS::: ' + str(len(contentData))
                                    #print 'TARGET CONTENT SIZE WANTED IS::::::::: ' + str(self.content_size_on_target)
                                    if self.content_size_on_target == len(contentData):
                                        self.all_target_data_rcvd = True
                                    else:
                                        self.content_size_on_target = self.content_size_on_target - len(contentData)
                                        #print 'WE ARE EXPECTING THIS MUCH DATA FOR TARGET ' + str(self.content_size_on_target)


                        if currently_using == 'target2' and self.haveTarget2Headers == False:
                            #print 'DONT HAVE TARGET2 HEADERS YET'
                            self.target2FullHeaders += data
                            if self.target2FullHeaders.find('\r\n\r\n') != -1:
                                #print 'GOT ALL TARGET 2 HEADERS'
                                self.haveTarget2Headers = True

                                # First the content range of this data is extracted from headers
                                contentRangePos = self.target2FullHeaders.find('Content-Range: bytes ') + 21
                                contentRange = ''
                                isStartRange = True
                                isEndRange = False
                                startRange = ''
                                endRange = ''                       

                                while 1:
                                    if self.target2FullHeaders[contentRangePos] == '/':
                                        break
                                    else:
                                        contentRange += self.target2FullHeaders[contentRangePos]
                                        if isStartRange:
                                            startRange += self.target2FullHeaders[contentRangePos]
                                        if isEndRange:
                                            endRange += self.target2FullHeaders[contentRangePos]
                                        if self.target2FullHeaders[contentRangePos] == '-':
                                            isEndRange = True
                                            isStartRange = False
                                        contentRangePos += 1

                                startRange = startRange[:-1]
                                self.content_size_on_target2 = int(endRange) - int(startRange) + 1

                                dataSplit = self.target2FullHeaders.splitlines()
                                endOfHeadersPos = 0
                                for p in dataSplit:
                                    endOfHeadersPos += len(p) + 2
                                    if p == '':
                                        break        

                                # Determines whether associated data was included        
                                if len(self.target2FullHeaders) != endOfHeadersPos:
                                    dataIncluded = True
                                elif len(self.target2FullHeaders) == endOfHeadersPos:
                                    dataIncluded = False

                                contentData = ''
                                # Here we extract data that came attached to the headers
                                if dataIncluded:
                                    #print 'SO THE DATA CAME WITH THE HEADERS ON ' + currently_using
                                    contentData = self.target2FullHeaders[endOfHeadersPos:]

                                    self.data_recvd_on_target2 += contentData
                                    #print 'LENGTH OF DATA ON HEADERS IS::: ' + str(len(contentData))
                                    #print 'TARGET2 CONTENT SIZE WANTED IS::::::::: ' + str(self.content_size_on_target2)  
                                    if self.content_size_on_target2 == len(contentData):
                                        self.all_target2_data_rcvd = True
                                    else:
                                        self.content_size_on_target2 = self.content_size_on_target2 - len(contentData)
                                        #print 'WE ARE EXPECTING THIS MUCH DATA FOR TARGET ' + str(self.content_size_on_target)

                        if self.all_target_data_rcvd and self.all_target2_data_rcvd:
                            dataLength = len(self.data_recvd_on_target) + len(self.data_recvd_on_target2)
                            self.final_msg += self.data_recvd_on_target
                            self.final_msg += self.data_recvd_on_target2
                            self.client.send(self.final_msg)
                            #print 'DATA LENGTH'
                            #print dataLength
                            #print '!!!!!!!!!!!!SENT!!!!!!!!!!!!!'
                            break

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
