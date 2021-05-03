# -*- coding: utf-8 -*-

from pymemcache.client.base import Client


class Store():
    def __init__(self, retry=3):
        self.client = Client(("localhost", 11211),
                             connect_timeout=1,
                             timeout=1)
        self.retry = retry

    def cache_get(self, key):
        for _ in range(self.retry):
            try:
                return self.client.get(key)
            except:
                pass

    def cache_set(self, key, val):
        for _ in range(self.retry):
            try:
                self.client.set(key, val)
            except:
                pass

    def get(self, key):
        for i in range(self.retry):
            try:
                return self.client.get(key)
            except:
                if i == self.retry - 1:
                    raise
