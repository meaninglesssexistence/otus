# -*- coding: utf-8 -*-

from pymemcache.client.base import Client as MemcacheClient


class Store():
    def __init__(self, host="localhost", port=11211, timeout=1, retry=3):
        self.client = MemcacheClient((host, port),
                                     connect_timeout=timeout,
                                     timeout=timeout)
        self.retry = retry

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        self.client.close()

    def cache_get(self, key):
        for _ in range(self.retry):
            try:
                return self.client.get(key)
            except:
                pass

    def cache_set(self, key, val, expire=0):
        for _ in range(self.retry):
            try:
                self.client.set(key, val, expire)
            except:
                pass

    def get(self, key):
        for i in range(self.retry):
            try:
                return self.client.get(key)
            except:
                if i == self.retry - 1:
                    raise
