from wsgi.tests import WSGIConnectorBaseTestCase
from wsgi.tests import start_response
from wsgi.tests import FakeSocket, FakeResponse


class WSGIConnectorTest(WSGIConnectorBaseTestCase):

    def setUp(self):
        self.connector = self.create_connector()

    def tearDown(self):
        self.shutdown()

    def test_write_errors(self):

        class FakeStream:
            def __init__(self):
                self.is_write_called = False

            def write(self, a):
                self.is_write_called = True
                raise TypeError

        errors = FakeStream()
        try:
            self.connector.write_errors(errors, '')
        except TypeError:
            self.assertTrue(errors.is_write_called)

    def test_chunked_request(self):
        env = self.create_environment({'HTTP_TRANSFER_ENCODING': 'chunked'})
        file = env['wsgi.input']
        file.write(bytearray(''.join(['2', chr(10) * 3,
                                      'aa', chr(10) * 2,
                                      '0', chr(10)]), 'utf-8'))
        file.seek(0)
        self.connector(env, start_response)
        self.assertTrue(FakeResponse.status.startswith('200'))

    def test_chunked_incorrect_request(self):
        env = self.create_environment({'HTTP_TRANSFER_ENCODING': 'chunked'})
        file = env['wsgi.input']
        file.write(bytearray(''.join(['p2', chr(10) * 3,
                                      'aa', chr(10) * 2,
                                      '0', chr(10)]), 'utf-8'))
        file.seek(0)
        self.connector(env, start_response)
        self.assertTrue(FakeResponse.status.startswith('500'))

    def test_redirect(self):
        env = self.create_environment({'HTTP_USER_AGENT': ''})
        FakeSocket.emulate_redirect = True
        self.connector(env, start_response)
        FakeSocket.emulate_redirect = False
        self.assertTrue(FakeResponse.status.startswith('304'))
        self.assertTrue('Location' in [h[0] for h in FakeResponse.headers])

    def test_internal_redirect(self):
        env = self.create_environment({'HTTP_USER_AGENT': 'UNTRUSTED'})
        FakeSocket.emulate_redirect = True

        self.connector(env, start_response)
        self.assertTrue(FakeResponse.status.startswith('200'))

        env = self.create_environment({'HTTP_USER_AGENT': 'UNTRUSTED'})
        FakeSocket.emulate_query = True
        self.connector(env, start_response)
        self.assertTrue(FakeResponse.status.startswith('200'))
        FakeSocket.emulate_query = False

        FakeSocket.emulate_redirect = False

    def test_internal_server_error(self):
        env = self.create_environment()
        FakeSocket.emulate_internal_server_error = True
        self.connector(env, start_response)
        self.assertTrue(FakeResponse.status.startswith('500'))
        FakeSocket.emulate_internal_server_error = False

    def test_socket_error(self):
        env = self.create_environment()
        FakeSocket.emulate_socket_error = True
        self.connector(env, start_response)
        self.assertTrue(FakeResponse.status.startswith('503'))
        FakeSocket.emulate_socket_error = False
