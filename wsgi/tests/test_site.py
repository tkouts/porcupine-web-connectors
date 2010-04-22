import inspect
import time
from os import path

from wsgi.tests import WSGIConnectorBaseTestCase


class TestWSGIConnectorSite(WSGIConnectorBaseTestCase):

    def setUp(self):
        self.shutdown()
        self.site = self.create_site()

    def tearDown(self):
        self.site.shutdown()

    def test_populate_with_incorrect_rejoin_timeout(self):
        this_file = inspect.currentframe().f_code.co_filename
        old_value = self.site.rejoin_timeout
        self.site.populate(path.join(path.dirname(this_file),
            "bad.server.ini"))
        self.assertEqual(old_value, self.site.rejoin_timeout)

    def test_populate(self):
        this_file = inspect.currentframe().f_code.co_filename
        self.site.populate(path.join(path.dirname(this_file),
            "good.server.ini"))
        self.assertEqual(20, self.site.rejoin_timeout)
        self.assertEqual(len(self.site), 2)

    def test_rejoin_node(self):
        self.site.rejoin_timeout = 2
        self.site.inactive_nodes.put(
            ('host1', time.time()))
        time.sleep(0.5)
        self.assertRaises(StopIteration, lambda: next(iter(self.site)))
        time.sleep(2.0)
        self.assertEqual('host1', next(iter(self.site)))

    def test_len(self):
        self.assertEqual(len(self.site), 0)

    def test_iter(self):
        self.site.add_host('host1')
        self.assertTrue('host1' in self.site)

    def test_remove_host(self):
        self.site.add_host('host1')
        self.site.add_host('host2')
        self.site.remove_host('host1')
        self.assertEqual(next(iter(self.site)), 'host2')

    def test_remove_incorrect_host(self):
        self.site.add_host('host1')
        self.site.add_host('host2')
        old_len = len(self.site)
        self.site.remove_host('host1_test')
        self.assertEqual(old_len, len(self.site))
