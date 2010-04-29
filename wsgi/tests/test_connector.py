import itertools
from wsgi.tests import WSGIConnectorBaseTestCase
from wsgi.tests import start_response
from wsgi.tests import FakeSocket, FakeResponse, FakeHost


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
        try:
            self.connector(env, start_response)
        finally:
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
        try:
            self.connector(env, start_response)
            self.assertTrue(FakeResponse.status.startswith('200'))
        finally:
            FakeSocket.emulate_query = False
            FakeSocket.emulate_redirect = False

    def test_internal_server_error(self):
        env = self.create_environment()
        FakeSocket.emulate_internal_server_error = True
        try:
            self.connector(env, start_response)
            self.assertTrue(FakeResponse.status.startswith('500'))
        finally:
            FakeSocket.emulate_internal_server_error = False

    def test_socket_error(self):
        env = self.create_environment()
        FakeSocket.emulate_socket_error = True
        try:
            self.connector(env, start_response)
            self.assertTrue(FakeResponse.status.startswith('503'))
        finally:
            FakeSocket.emulate_socket_error = False

    def test_host_refused_connection(self):
        env = self.create_environment()
        old_seq = FakeSocket.default_socket_seq
        FakeSocket.default_socket_seq = [3]
        old_hosts = self.connector.site._hosts[:]
        try:
            self.connector.site.add_host(FakeHost())
            self.connector.site.add_host(FakeHost())
            old_len = len(self.connector.site)
            self.connector(env, start_response)
            self.assertEqual(old_len - 1, len(self.connector.site))
        finally:
            FakeSocket.default_socket_seq = old_seq
            self.connector.site._hosts = old_hosts
            self.connector.site.hosts = itertools.cycle(old_hosts)

    def test_host_refused_connection_with_one_host(self):
        env = self.create_environment()
        old_seq = FakeSocket.default_socket_seq
        FakeSocket.default_socket_seq = [3]
        try:
            errors = env['wsgi.errors']
            self.connector(env, start_response)
            errors.seek(0)
            self.assertTrue(b'SocketError' in b''.join(errors.readlines()))
        finally:
            FakeSocket.default_socket_seq = old_seq

    def test_empty_query_string(self):
        env = self.create_environment({'HTTP_USER_AGENT': 'UNTRUSTED'})
        FakeSocket.emulate_redirect = True
        old_location = FakeSocket.default_location
        FakeSocket.default_location = 'object_id'
        try:
            self.connector(env, start_response)
            self.assertEqual(env['QUERY_STRING'], '')
        finally:
            FakeSocket.emulate_redirect = False
            FakeSocket.default_location = old_location
