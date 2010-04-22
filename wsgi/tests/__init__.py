import imp
import tempfile
import unittest
from errno import EISCONN, EADDRINUSE

try:
    # python 2.6
    from cPickle import dumps
except ImportError:
    # python 3.0
    from pickle import dumps
try:
    import __builtin__
except ImportError:
    import builtins as __builtin__  # python 3.0

# for mocking purposes don't change the line below
import wsgi.WSGIConnector


class WSGIConnectorBaseTestCase(unittest.TestCase):
    @staticmethod
    def create_environment(headers={'CONTENT_LENGTH': 100}):
        environ = {'PATH_INFO': '/',
                   'SCRIPT_NAME': '',
                   'HTTP_USER_AGENT': '',
                   'HTTP_HOST': 'localhost',

                   'wsgi.errors': tempfile.TemporaryFile(),
                   'wsgi.input': tempfile.TemporaryFile(),
                   'wsgi.url_scheme': 'http',
                   'wsgi.file_wrapper': None}
        environ.update(headers)
        return environ

    @staticmethod
    def create_connector():
        connector = wsgi.WSGIConnector.WSGIConnector()
        return connector

    @staticmethod
    def shutdown():
        wsgi.WSGIConnector.shutdown()

    @staticmethod
    def create_site():
        # create new un-populated site
        site = wsgi.WSGIConnector.Site()
        return site


class FakeResponse:
    status = ''
    headers = {}


def start_response(status, headers):
    FakeResponse.status = status
    FakeResponse.headers = headers


class FakeSocket:
    emulate_redirect = False
    emulate_query = False
    emulate_socket_error = False
    emulate_internal_server_error = False
    recv_gen = None

    def __init__(self):
        self.gen = iter([EADDRINUSE, 0, EISCONN])
        location = ('', 'object_id?cmd=login')[self.emulate_query]

        if FakeSocket.recv_gen is None:
            if self.emulate_redirect:
                FakeSocket.recv_gen = iter([
                    dumps([304, '',
                           {'Location': location},
                           []]), '',
                    dumps([200, '',
                           {'Content-Type': 'text/html; charset=utf-8'},
                           ['cookie']]), None])

            elif self.emulate_internal_server_error:
                FakeSocket.recv_gen = iter(['nonsense', None])

            else:  # OK response
                FakeSocket.recv_gen = iter([
                    dumps([200, '',
                           {'Content-Type': 'text/html; charset=utf-8'},
                           ['cookie']]), None])

    def connect_ex(self, a):
        return next(self.gen)

    def recv(self, a):
        if self.emulate_socket_error:
            FakeSocket.recv_gen = None
            raise SocketError

        n = next(FakeSocket.recv_gen)
        if n is None:
            # end of recv sequence
            FakeSocket.recv_gen = None
        return  n

    close = lambda a: False
    bind = lambda a, b: False
    send = lambda a, b: False
    shutdown = lambda a, b: False


class SocketError(Exception):
    pass


class FakeSocketModule:
    AF_INET = 0
    SOCK_STREAM = 0
    SHUT_WR = 0
    socket = lambda a, b, c: FakeSocket()
    error = SocketError
    gethostbyname = lambda a, b: False
    gethostname = lambda a: False


class FakeHost:
    address = None
    connections = 0
    port = iter([0, 1])


# patch import
old_import = __builtin__.__import__


def fake_import(*args, **kwargs):
    name = args[0]
    if name == 'socket':
        return FakeSocketModule()
    return old_import(*args, **kwargs)


__builtin__.__import__ = fake_import
# shutdown existing site
wsgi.WSGIConnector.shutdown()
imp.reload(wsgi.WSGIConnector)
