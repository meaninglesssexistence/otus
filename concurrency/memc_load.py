#!/usr/bin/env python
# -*- coding: utf-8 -*-
import os
import gzip
import sys
import glob
import logging
import collections
from optparse import OptionParser
# brew install protobuf
# protoc  --python_out=. ./appsinstalled.proto
# pip install protobuf
import appsinstalled_pb2
# pip install python-memcached
import memcache
import threading
import time

NORMAL_ERR_RATE = 0.01
AppsInstalled = collections.namedtuple("AppsInstalled", ["dev_type", "dev_id", "lat", "lon", "apps"])


class MemCacheClient(threading.Thread):
    def __init__(self, addr, retry_attempt=3, socket_timeout=3):
        threading.Thread.__init__(self)
        self.addr = addr
        self.retry_attempt = retry_attempt
        self.client = memcache.Client([addr], socket_timeout=socket_timeout)
        self.condition = threading.Condition()
        self.items = {}
        self.processed = self.errors = 0

    def set(self, key, value):
        with self.condition:
            self.items[key] = value
            self.condition.notify()

    def end(self):
        self.set(None, None)

    def reset_stat(self):
        self.processed = self.errors = 0

    def run(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.items)
                items = self.items
                self.items = {}

            is_end = False
            if None in items:
                is_end = True
                items.pop(None, None)

            if items:
                self._send(items)

            if is_end:
                return

    def _send(self, items):
        for attempt in range(self.retry_attempt):
            try:
                self.client.set_multi(items)
                self.processed += len(items)
                return
            except Exception as e:
                if attempt == self.retry_attempt - 1:
                    logging.exception("Cannot write to memc %s: %s" % (self.addr, e))
                    self.error += len(items)


def dot_rename(path):
    head, fn = os.path.split(path)
    # atomic in most cases
    os.rename(path, os.path.join(head, "." + fn))


def insert_appsinstalled(memc_client, appsinstalled, dry_run=False):
    ua = appsinstalled_pb2.UserApps()
    ua.lat = appsinstalled.lat
    ua.lon = appsinstalled.lon
    key = "%s:%s" % (appsinstalled.dev_type, appsinstalled.dev_id)
    ua.apps.extend(appsinstalled.apps)
    packed = ua.SerializeToString()
    if dry_run:
        logging.debug("%s - %s -> %s" % (memc_addr, key, str(ua).replace("\n", " ")))
    else:
        memc_client.set(key, packed)


def parse_appsinstalled(line):
    line_parts = line.strip().split("\t")
    if len(line_parts) < 5:
        return
    dev_type, dev_id, lat, lon, raw_apps = line_parts
    if not dev_type or not dev_id:
        return
    try:
        apps = [int(a.strip()) for a in raw_apps.split(",")]
    except ValueError:
        apps = [int(a.strip()) for a in raw_apps.split(",") if a.isidigit()]
        logging.info("Not all user apps are digits: `%s`" % line)
    try:
        lat, lon = float(lat), float(lon)
    except ValueError:
        logging.info("Invalid geo coords: `%s`" % line)
    return AppsInstalled(dev_type, dev_id, lat, lon, apps)


def print_statistics(device_memc, common_errors):
    processed = 0
    errors = common_errors

    for memc_client in device_memc.values():
        processed += memc_client.processed
        errors += memc_client.errors

    if not processed:
        return

    err_rate = float(errors) / processed
    if err_rate < NORMAL_ERR_RATE:
        logging.info("Acceptable error rate (%s). Successfull load" % err_rate)
    else:
        logging.error("High error rate (%s > %s). Failed load" % (err_rate, NORMAL_ERR_RATE))

    for memc_client in device_memc.values():
        memc_client.reset_stat()


def main(options):
    device_memc = {
        "idfa": MemCacheClient(options.idfa),
        "gaid": MemCacheClient(options.gaid),
        "adid": MemCacheClient(options.adid),
        "dvid": MemCacheClient(options.dvid),
    }

    for memc_client in device_memc.values():
        memc_client.start()

    try:
        for fn in glob.iglob(options.pattern):
            errors = 0
            logging.info('Processing %s' % fn)
            fd = gzip.open(fn)
            for line in fd:
                line = line.decode('utf-8').strip()
                if not line:
                    continue
                appsinstalled = parse_appsinstalled(line)
                if not appsinstalled:
                    errors += 1
                    continue
                memc_client = device_memc.get(appsinstalled.dev_type)
                if not memc_client:
                    errors += 1
                    logging.error("Unknow device type: %s" % appsinstalled.dev_type)
                    continue
                insert_appsinstalled(memc_client, appsinstalled, options.dry)
            fd.close()
            dot_rename(fn)

            print_statistics(device_memc, errors)
    finally:
        for memc_client in device_memc.values():
            memc_client.end()

        for memc_client in device_memc.values():
            memc_client.join()


def prototest():
    sample = "idfa\t1rfw452y52g2gq4g\t55.55\t42.42\t1423,43,567,3,7,23\ngaid\t7rfw452y52g2gq4g\t55.55\t42.42\t7423,424"
    for line in sample.splitlines():
        dev_type, dev_id, lat, lon, raw_apps = line.strip().split("\t")
        apps = [int(a) for a in raw_apps.split(",") if a.isdigit()]
        lat, lon = float(lat), float(lon)
        ua = appsinstalled_pb2.UserApps()
        ua.lat = lat
        ua.lon = lon
        ua.apps.extend(apps)
        packed = ua.SerializeToString()
        unpacked = appsinstalled_pb2.UserApps()
        unpacked.ParseFromString(packed)
        assert ua == unpacked


if __name__ == '__main__':
    op = OptionParser()
    op.add_option("-t", "--test", action="store_true", default=False)
    op.add_option("-l", "--log", action="store", default=None)
    op.add_option("--dry", action="store_true", default=False)
    op.add_option("--pattern", action="store", default="/data/appsinstalled/*.tsv.gz")
    op.add_option("--idfa", action="store", default="127.0.0.1:33013")
    op.add_option("--gaid", action="store", default="127.0.0.1:33014")
    op.add_option("--adid", action="store", default="127.0.0.1:33015")
    op.add_option("--dvid", action="store", default="127.0.0.1:33016")
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.INFO if not opts.dry else logging.DEBUG,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    if opts.test:
        prototest()
        sys.exit(0)

    logging.info("Memc loader started with options: %s" % opts)
    try:
        start_time = time.time()
        main(opts)
        logging.info("Processing took %s seconds" % (time.time() - start_time))
    except Exception as e:
        logging.exception("Unexpected error: %s" % e)
        sys.exit(1)
