# -*- coding: utf-8 -*-

from pymemcache.client.base import Client as MemcacheClient
from time import sleep


class Store():
    def __init__(self, host="localhost", port=11211, timeout=1,
                 retry=3, retry_timeout=1):
        self.client = MemcacheClient((host, port),
                                     connect_timeout=timeout,
                                     timeout=timeout)
        self.retry = retry
        self.retry_timeout = retry_timeout

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
                sleep(self.retry_timeout)

    def cache_set(self, key, val, expire=0):
        for _ in range(self.retry):
            try:
                self.client.set(key, val, expire)
            except:
                sleep(self.retry_timeout)

    def get(self, key):
        for i in range(self.retry):
            try:
                return self.client.get(key)
            except:
                if i == self.retry - 1:
                    raise
                sleep(self.retry_timeout)
