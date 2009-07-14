#===============================================================================
#    Copyright 2005-2009, Tassos Koutsovassilis
#
#    This file is part of Porcupine.
#    Porcupine is free software; you can redistribute it and/or modify
#    it under the terms of the GNU Lesser General Public License as published by
#    the Free Software Foundation; either version 2.1 of the License, or
#    (at your option) any later version.
#    Porcupine is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU Lesser General Public License for more details.
#    You should have received a copy of the GNU Lesser General Public License
#    along with Porcupine; if not, write to the Free Software
#    Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA
#===============================================================================
"Porcupine CGI connector"
import sys
import os
import socket
from cPickle import dumps
from ConfigParser import RawConfigParser

def getAddressFromString(sAddress):
    address = sAddress.split(':')
    address[1] = int(address[1])
    return tuple(address)

config = RawConfigParser()
config.readfp(open('server.ini'))
hosts = config.get('config', 'hosts')
hosts = hosts.split(',')
ADDR = getAddressFromString(hosts[0])
BUFSIZ = 8192
HTMLCodes = (('&', '&amp;'),
             ('<', '&lt;'),
             ('>', '&gt;'),
             ('"', '&quot;'))

def getResponse():
    try:
        # MS Windows: no special translation of end-of-lines
        if os.name=='nt':
            import msvcrt
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
            msvcrt.setmode(sys.stdin.fileno(), os.O_BINARY)
        requestBody=''
        if os.environ.has_key('CONTENT_LENGTH'):
            length = int(os.environ['CONTENT_LENGTH'])
            if length:
                requestBody = sys.stdin.read(length)
        dict = {
            'if': 'CGI',
            'env': os.environ.data,
            'inp': requestBody
	}
        # send the request to Porcupine Server
        data = dumps(dict)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect(ADDR)
        s.send(data)
        s.shutdown(1)
        # get the response
        while 1:
            rdata = s.recv(BUFSIZ)
            if not rdata:
                break
            sys.stdout.write(rdata)
        s.close()
    except:
        import traceback
        output = traceback.format_exception(*sys.exc_info())
        output = ''.join(output)
        output = HTMLEncode(output)
        sys.stdout.write('''Content-Type: text/html

<html><body>
<H3>Porcupine Server</H3>
<p><pre>ERROR

%s</pre>
</body></html>\n''' % output)

def HTMLEncode(s, codes=HTMLCodes):
    for code in codes:
        s = s.replace(code[0], code[1])
    return s

getResponse()