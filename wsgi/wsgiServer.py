"Porcupine WSGI sever based on wsgiref"
from wsgiref.simple_server import make_server
import WSGIConnector

port = 1088
httpd = make_server('', port, WSGIConnector.application)
print('Serving on port %d' % port)
httpd.serve_forever()
