# -*- coding: utf-8 -*-

import subprocess
import unittest

from app.store import Store


class TestSuite(unittest.TestCase):
    MEMC_PORT = 11211

    def setUp(self):
        self.context = {}
        self.memc_proc = subprocess.Popen([
            'memcached', '-p', str(TestSuite.MEMC_PORT)
        ])

    def tearDown(self):
        self.kill_memc()

    def kill_memc(self):
        if self.memc_proc.poll() is None:
            self.memc_proc.kill()
            self.memc_proc.wait()

    def test_store_cache_get(self):
        """ Проверяем получение значения из кеша при наличии и отсутствии
            соединения с реальным сервером Memcache.
        """
        with Store(host="localhost", port=TestSuite.MEMC_PORT) as store:
            store.cache_set("key", '42')
            self.assertEqual(store.cache_get("key"), b'42')
            self.kill_memc()
            self.assertIsNone(store.cache_get("key"))

    def test_store_cache_set(self):
        """ Проверяем сохранение значения в кеше при наличии и отсутствии
            соединения с реальным сервером Memcache.
        """
        with Store(host="localhost", port=TestSuite.MEMC_PORT) as store:
            self.kill_memc()
            self.assertIsNone(store.cache_set("key", '42'))

    def test_store_get(self):
        """ Проверяем получени значения из 'key-value' storage при наличии
            и отсутствии соединения с сервером.
        """
        with Store(host="localhost", port=TestSuite.MEMC_PORT) as store:
            store.cache_set("key", '42')
            self.assertEqual(store.get("key"), b'42')
            self.kill_memc()
            self.assertRaises(Exception, store.get, "key")

if __name__ == "__main__":
    unittest.main()
