# -*- coding: utf-8 -*-

from unittest import TestCase
from unittest import main as run_test
from unittest.mock import Mock
from app.store import Store


class TestSuite(TestCase):
    def test_store_cache_get(self):
        _self = Mock()
        _self.retry = 3
        _self.client.get.return_value = 42
        self.assertEqual(Store.cache_get(_self, "key"), 42)
        _self.client.get.side_effect = Exception
        self.assertIsNone(Store.cache_get(_self, "key"))

    def test_store_cache_set(self):
        _self = Mock()
        _self.retry = 3
        _self.client.set.return_value = None
        self.assertEqual(Store.cache_set(_self, "key", 42), None)
        _self.client.set.side_effect = Exception
        self.assertIsNone(Store.cache_set(_self, "key", 42))

    def test_store_get(self):
        _self = Mock()
        _self.retry = 3
        _self.client.get.return_value = 42
        self.assertEqual(Store.get(_self, "key"), 42)
        _self.client.get.side_effect = Exception
        self.assertRaises(Exception, Store.get, _self, "key")

if __name__ == "__main__":
    run_test()
