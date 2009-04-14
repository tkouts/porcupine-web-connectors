"Porcupine WSGI connector"

import socket
import sys
import ConfigParser
import os
import urllib
import re
from errno import EISCONN, EADDRINUSE
from threading import RLock
from cPickle import dumps, loads

BUFSIZ = 8*1024
HTMLCodes = (('&', '&amp;'),
             ('<', '&lt;'),
             ('>', '&gt;'),
             ('"', '&quot;'))
IP_ADDR = socket.gethostbyname(socket.gethostname())
MOBILE_BROWSER_SIGNATURE = re.compile('PMB|UNTRUSTED')
PORT_RANGE = range(65535, 40958, -1)
NEXT_HOST_LOCK = RLock()
ERROR_PAGE = '''<html><body><H3>Porcupine Server</H3><p><pre>
ERROR

%s
</pre>
</p>
</body></html>'''

HTTP_CODES = {200: '200 OK',
              302: '302 Found',
              304: '304 Not Modified',
              404: '404 Not Found',
              403: '403 Forbidden',
              500: '500 Internal Server Error',
              501: '501 Not Implemented'}

class Host(object):
    def __init__(self, address):
        self.address = address
        self.connections = 0
        self.tot = 0
        self.port = self.getPort()

    def getPort(self):
        while True:
            for port in PORT_RANGE:
                yield(port)

class Site(object):
    def __init__(self):
        self.isPopulated = False

    def populate(self, iniFile):
        config = ConfigParser.RawConfigParser()
        config.readfp(open(iniFile))
        self.__hosts = []
        hosts = config.get('config', 'hosts')
        hosts = hosts.split(',')
        for host in hosts:
            self.__hosts.append(Host(self.getAddressFromString(host)))
        self.isPopulated = True
        self.__rrcounter = -1

    def getNumOfHosts(self):
        return len(self.__hosts)

    def getAddressFromString(self, sAddress):
        address = sAddress.split(':')
        address[1] = int(address[1])
        return tuple(address)
        
    def getNextHost(self):
        # round robin
        NEXT_HOST_LOCK.acquire()
        next = self.__rrcounter = (self.__rrcounter + 1) % len(self.__hosts)
        NEXT_HOST_LOCK.release()
        return self.__hosts[next:] + self.__hosts[0:next]
    
SITE=Site()
inifile = os.path.dirname(__file__) + '/server.ini'
SITE.populate(inifile)

class WSGIConnector:
    def __init__(self, environ, start_response):
        self.environment = environ
        self.start = start_response

    def HTMLEncode(self, s, codes=HTMLCodes):
        for code in codes:
            s = s.replace(code[0], code[1])
        return s
        
    def __iter__(self):
        response_headers = []
        response_body = ''
        
        length = 0
        if self.environment["CONTENT_LENGTH"]:
            length = int(self.environment["CONTENT_LENGTH"])

        #print self.environment['HTTP_USER_AGENT']
        
        errors = self.environment.pop('wsgi.errors')
        
        if self.environment.has_key('wsgi.input'):
            wsgi_input = self.environment.pop('wsgi.input')
            if length > 0:
                input = wsgi_input.read(length)
            else:
                # chunked request
                input = []
                
                if self.environment.has_key('HTTP_TRANSFER_ENCODING') and \
                        self.environment['HTTP_TRANSFER_ENCODING'] == 'chunked':
                    chunk_size = int('0x' + wsgi_input.readline(), 16)
                    
                    while chunk_size > 0:
                        char = wsgi_input.read(1)
                        while char in '\r\n':
                            char = wsgi_input.read(1)    
    
                        input.append(char)
                        input.append(wsgi_input.read(chunk_size - 1))
                        
                        char = wsgi_input.read(1)
                        while char in '\r\n':
                            char = wsgi_input.read(1) 
                        
                        chunk_size = int('0x' + char + wsgi_input.readline(), 16)
                
                input = ''.join(input)
        else:
            input = ''

        self.environment["PATH_INFO"] = urllib.unquote(self.environment["PATH_INFO"])

        dict = {
            'if': 'WSGI',
            'env': self.environment,
            'inp': input
        }
        data = dumps(dict, 2)
        
        try:
            while True:
                hosts = SITE.getNextHost()
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                try:
                    for host in hosts:
                        err = s.connect_ex(host.address)
                        while not err in (0, EISCONN):
                            if err == EADDRINUSE:  # address already in use
                                # the ephemeral port range is exhausted
                                s.close()
                                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                                s.bind((IP_ADDR, host.port.next()))
                            else:
                                # the host refuses conncetion
                                break
                            err = s.connect_ex(host.address)
                        else:
                            # we got a connection
                            host.connections += 1
                            host.tot += 1
                            break
    
                    # Send our request to Porcupine Server
                    s.send(data)
                    s.shutdown(1)
    
                    # Get the response object from Porcupine Server
                    response = []
                    while True:
                        rdata = s.recv(BUFSIZ)
                        if not rdata:
                            response = ''.join(response)
                            break
                        response.append(rdata)
                    break
                finally:
                    s.close()
                    host.connections -= 1

            ret_code, body, headers, cookies = loads(response)
            
            if not headers.has_key('Location'):
                for header in headers.items():
                    response_headers.append(header)
                for cookie in cookies:
                    response_headers.append(('Set-Cookie', cookie))
            else:
                # it is a redirect
                if MOBILE_BROWSER_SIGNATURE.search(
                        self.environment['HTTP_USER_AGENT']):
                    # it is a mobile device
                    # handle redirect internally
                    url_scheme = self.environment['wsgi.url_scheme']
                    sLocation = headers['Location']
                    if sLocation[:len(url_scheme)] != url_scheme:
                        sLocation = url_scheme + '://' + \
                                    self.environment['HTTP_HOST'] + sLocation
                        
                    sHost = self.environment['HTTP_HOST'] + \
                            self.environment['SCRIPT_NAME']
					
                    lstPath = sLocation[
                        sLocation.index(sHost) + len(sHost):].split('?')
                    
                    self.environment['PATH_INFO'] = lstPath[0]
                    
                    if len(lstPath)==2:
                        self.environment['QUERY_STRING'] = lstPath[1]
                    else:
                        self.environment['QUERY_STRING'] = ''
                        
                    self.environment['wsgi.errors'] = errors
                    
                    conn = WSGIConnector(self.environment, self.start)
                    for r in iter(conn):
                        yield r
                    return
                else:
                    # it is a redirect
                    response_headers.append( ('Location', headers['Location']) )
                
        except socket.error, e:
            import traceback
            output = traceback.format_exception(*sys.exc_info())
            output = ''.join(output)
            errors.write(output)
            ret_code = 503
            response_headers = [('Content-Type', 'text/html')]
            body = ERROR_PAGE % 'Service Temporarily Unavailable'

        except:
            import traceback
            output = traceback.format_exception(*sys.exc_info())
            output = ''.join(output)
            output = self.HTMLEncode(output)
            errors.write(output)
            ret_code = 500
            response_headers = [('Content-Type', 'text/html')]
            body = ERROR_PAGE % output

        response_headers.append( ('Content-Length', str(len(body))) )

        self.start(HTTP_CODES[ret_code], response_headers)
        
        yield body
