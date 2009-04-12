from wsgiutils import wsgiServer
import WSGIConnector

server = wsgiServer.WSGIServer (('localhost', 1088), {'/': WSGIConnector.WSGIConnector})
server.serve_forever()
