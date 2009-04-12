"Porcupine WSGI connector"

import socket, sys, ConfigParser, os, urllib
from errno import EISCONN, EADDRINUSE
from threading import RLock
from cPickle import dumps, loads

BUFSIZ = 8*1024
HTMLCodes = [
    ['&', '&amp;'],
    ['<', '&lt;'],
    ['>', '&gt;'],
    ['"', '&quot;'],
]
IP_ADDR = socket.gethostbyname(socket.gethostname())
PORT_RANGE = range(65535, 40958, -1)
NEXT_HOST_LOCK = RLock()
ERROR_PAGE = '''<html><body>
<H3>Porcupine Server</H3>
<p>
<pre>
ERROR

%s
</pre>
</p>
</body></html>'''

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

    def HTMLEncode(s, codes=HTMLCodes):
        for code in codes:
            s = s.replace(code[0], code[1])
        return s
        
    def __iter__(self):

        status = '200 OK'
        response_headers = []
        response_body = ''

        length = int('0' + self.environment["CONTENT_LENGTH"])
        
        errors = self.environment.pop('wsgi.errors')
        input = '' + self.environment.pop('wsgi.input').read(length)

        self.environment["PATH_INFO"] = urllib.unquote(self.environment["PATH_INFO"])

        dict = {
            'if': 'WSGI',
            'env': self.environment,
            'inp': input
        }
        data = dumps(dict)
        
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

            tplResponse = tuple( response.split('\n\n---END BODY---\n\n') )
            headers = loads(tplResponse[1])
    
            if not(headers.has_key('Location')):
                # it is not a redirect
                for header in headers.items():
                    response_headers.append(header)

                #cookies
                if len(tplResponse) > 2:
                    cookies = loads(tplResponse[2])
                    for cookie in cookies:
                        response_headers.append( ('Set-Cookie', cookie) )
    
                response_body = tplResponse[0]
            else:
                # it is a redirect
                response_headers.append( ('Location', headers['Location']) )
                status = '302 Found'
        
        except socket.error, e:
            import traceback
            output = traceback.format_exception(*sys.exc_info())
            output = ''.join(output)
            errors.write(output)
            status = '503 Service Temporarily Unavailable'
            response_headers = [('Content-Type', 'text/html')]
            response_body = ERROR_PAGE % 'Service Temporarily Unavailable'

        except:
            import traceback
            output = traceback.format_exception(*sys.exc_info())
            output = ''.join(output)
            output = self.HTMLEncode(output)
            errors.write(output)
            response_headers = [('Content-Type', 'text/html')]
            response_body = ERROR_PAGE % output

        response_headers.append( ('Content-Length', str(len(response_body))) )

        self.start(status, response_headers)
        yield response_body


