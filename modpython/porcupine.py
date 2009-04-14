"Porcupine MOD_PYTHON connector"

import socket, sys, ConfigParser, os
import re
from errno import EISCONN, EADDRINUSE
from threading import RLock
from cPickle import dumps, loads
from mod_python import apache

BUFSIZ = 8*1024
HTMLCodes = [
    ['&', '&amp;'],
    ['<', '&lt;'],
    ['>', '&gt;'],
    ['"', '&quot;'],
]
IP_ADDR = socket.gethostbyname(socket.gethostname())
MOBILE_BROWSER_SIGNATURE = re.compile('MIDP|UNTRUSTED')
PORT_RANGE = range(65535, 40958, -1)
NEXT_HOST_LOCK = RLock()
#WEB_LOG = open('C:/www/web.log', 'w+')

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
        # least connections
#        self.__hosts.sort(self.sort)
#        return(self.__hosts)
#        NEXT_HOST_LOCK.acquire()
#        conns = [host.connections for host in self.__hosts]
#        NEXT_HOST_LOCK.release()
#        pairs = zip(conns, self.__hosts)
#        pairs.sort()
#        hosts = [x[1] for x in pairs]
#        return(hosts)
            

SITE=Site()
inifile = os.path.dirname(__file__) + '/server.ini'
SITE.populate(inifile)

def handler(req):
    req.add_common_vars()
    # construct the environment dictionary
    environ = {}
    for sVar in req.subprocess_env.keys():
        environ[sVar] = req.subprocess_env[sVar]

    return handleRequest(req, environ)            


def handleRequest(req, environ):
    try:
        # get input
        requestBody = req.read()
        dict = {
            'if': 'MOD_PYTHON',
            'env': environ,
            'inp': requestBody
        }
        data = dumps(dict, 2)

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
                #WEB_LOG.write('closing connection for host %s. Total conns:%d\n' %(host.address, host.tot))
                #WEB_LOG.flush()

        ret_code, body, headers, cookies = loads(response)
        req.status = ret_code
        
        if not headers.has_key('Location'):
            # it is not a redirect
            req.content_type = headers.pop('Content-Type')
            req.headers_out['Content-Length'] = str(len(body))
            for cookie in cookies:
                req.headers_out.add('Set-Cookie', cookie)
            for header in headers:
                req.headers_out[header] = headers[header]
            req.send_http_header()
            req.write(body)
        else:
            # it is a redirect
            if MOBILE_BROWSER_SIGNATURE.search( environ['HTTP_USER_AGENT'] ):
                # it is a mobile device
                # handle redirect internally
                sLocation = headers['Location']
                sScriptName = environ['SCRIPT_NAME']
                
                lstPath = sLocation[
                    sLocation.index(sScriptName) + len(sScriptName):].split('?')
                
                environ['PATH_INFO'] = lstPath[0]
                if len(lstPath)==2:
                    environ['QUERY_STRING'] = lstPath[1]
                return handleRequest(req, environ) 
            else:                
                req.headers_out['Location'] = headers['Location']
                req.send_http_header()
        
        return apache.OK

    except socket.error, e:
        import traceback
        output = traceback.format_exception(*sys.exc_info())
        output = ''.join(output)
        return apache.HTTP_SERVICE_UNAVAILABLE

    except:
        import traceback
        output = traceback.format_exception(*sys.exc_info())
        output = ''.join(output)
        output = HTMLEncode(output)
        req.content_type = 'text/html'
        req.write('''
<html><body>
<H3>Porcupine Server</H3>
<p>
<pre>
ERROR

%s
</pre>
</p>
</body></html>
''' % output)
        return apache.OK

def HTMLEncode(s, codes=HTMLCodes):
    for code in codes:
        s = s.replace(code[0], code[1])
    return s
