import imp
import sys
import collections

try:
    import __builtin__
except ImportError:
    import builtins as __builtin__  # python 3.0

from wsgi.tests import WSGIConnectorBaseTestCase
from wsgi.tests import start_response


class TestWSGIConnectorGlobals(WSGIConnectorBaseTestCase):

    def setUp(self):
        self.connector = self.create_connector()
        self.application = sys.modules[self.connector.__module__].application

    def tearDown(self):
        self.shutdown()

    def test_application_type(self):
        env = self.create_environment()
        self.assertTrue(isinstance(self.application(env, start_response),
            collections.Iterable))

    def test_shutdown(self):
        env = self.create_environment()
        self.application(env, start_response)
        self.shutdown()
        self.assertEqual(self.connector.site._rejoin_thread.is_alive(), False)

    def test_imports(self):
        old_import = __builtin__.__import__
        fakes = {'Queue': False, 'cPickle': False, 'httplib': False,
                 'urllib': False, 'configparser': False}

        def fake_import(*args, **kwargs):
            name = args[0]
            if name in fakes and not fakes[name]:
                fakes[name] = True
                raise ImportError
            return old_import(*args, **kwargs)

        import wsgi.WSGIConnector

        __builtin__.__import__ = fake_import
        is_all_proceeded = lambda: all(fakes[name] for name in fakes)

        while not is_all_proceeded():
            try:
                self.shutdown()
                imp.reload(wsgi.WSGIConnector)
            except ImportError:
                pass

        self.assertTrue(is_all_proceeded())

        __builtin__.__import__ = old_import
        self.shutdown()
        imp.reload(wsgi.WSGIConnector)
