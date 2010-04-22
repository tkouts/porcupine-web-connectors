#!/usr/bin/env python
"Porcupine WSGI sever based on wsgiref"
from wsgiref.simple_server import make_server
import WSGIConnector

port = 1088
httpd = make_server('', port, WSGIConnector.application)
print('Serving on port %d' % port)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    WSGIConnector.shutdown()
