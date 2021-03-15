#!/usr/bin/env python
# -*- coding: utf-8 -*-


import datetime
import tempfile
import unittest

from log_analyzer import find_log, report_exists, parse_log, count_stats, render_report, read_config
from os import path
from pathlib import Path

class TestLogAnalyzer(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.test_path = self.test_dir.name

    def tearDown(self):
        self.test_dir.cleanup()

    def test_find_log_empty(self):
        self.assertIsNone(find_log(self.test_path))

    def test_find_log_match_plain(self):
        Path(path.join(self.test_path, 'nginx-access-ui.log-20170630')).touch()
        Path(path.join(self.test_path, 'nginx-access-ui.log-20170530')).touch()
        Path(path.join(self.test_path, 'nginx-access-ui.log-20177730')).touch()

        log = find_log(self.test_path)
        self.assertEqual(log.path, path.join(self.test_path, 'nginx-access-ui.log-20170630'))
        self.assertEqual(log.date, datetime.date(2017, 6, 30))
        self.assertFalse(log.is_gz)

    def test_find_log_match_gz(self):
        Path(path.join(self.test_path, 'nginx-access-ui.log-20170630.bz2')).touch()
        Path(path.join(self.test_path, 'nginx-access-ui.log-20170530.gz')).touch()
        Path(path.join(self.test_path, 'nginx-access-ui.log-20170529')).touch()

        log = find_log(self.test_path)
        self.assertEqual(log.path, path.join(self.test_path, 'nginx-access-ui.log-20170530.gz'))
        self.assertEqual(log.date, datetime.date(2017, 5, 30))
        self.assertTrue(log.is_gz)

    def test_report_exists(self):
        Path(path.join(self.test_path, 'report-2017.01.02.html')).touch()

        self.assertFalse(report_exists(self.test_path, datetime.date(2018, 1, 2)))
        self.assertTrue(report_exists(self.test_path, datetime.date(2017, 1, 2)))

    def test_parse_log_empty(self):
        log_path = path.join(self.test_path, 'nginx-access-ui.log-20170530')
        Path(log_path).touch()

        log = list(parse_log(log_path, False))
        self.assertListEqual(log, [])

    def test_parse_log(self):
        log_path = path.join(self.test_path, 'nginx-access-ui.log-20170530')
        with open(log_path, "w") as f:
            f.write('1.196.116.32 -  - [29/Jun/2017:03:50:22 +0300] "GET /api/v2/banner/25019354 HTTP/1.1" 200 927 "-" "Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5" "-" "1498697422-2190034393-4708-9752759" "dc7161be3" 0.390\n')
            f.write('1.99.174.176 3b81f63526fa8  - [29/Jun/2017:03:50:22 +0300] "GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1" 200 12 "-" "Python-urllib/2.7" "-" "1498697422-32900793-4708-9752770" "-" 0.133\n')
            f.write('1.169.137.128 -  - [29/Jun/2017:03:50:22 +0300] "0" 400 19415 "-" "Slotovod" "-" "1498697422-2118016444-4708-9752769" "712e90144abee9" 0.199\n')

        log = list(parse_log(log_path, False))
        self.assertListEqual(log, [
            ('1.196.116.32', '-', '-', '[29/Jun/2017:03:50:22 +0300]', '"GET /api/v2/banner/25019354 HTTP/1.1"', '200', '927', '"-"', '"Lynx/2.8.8dev.9 libwww-FM/2.14 SSL-MM/1.4.1 GNUTLS/2.10.5"', '"-"', '"1498697422-2190034393-4708-9752759"', '"dc7161be3"', '0.390'),
            ('1.99.174.176', '3b81f63526fa8', '-', '[29/Jun/2017:03:50:22 +0300]', '"GET /api/1/photogenic_banners/list/?server_name=WIN7RB4 HTTP/1.1"', '200', '12', '"-"', '"Python-urllib/2.7"', '"-"', '"1498697422-32900793-4708-9752770"', '"-"', '0.133'),
            None
        ])

    def test_count_stats(self):
        log = [('', '', '', '', '"GET /url/1 HTTP/1.1"', '', '', '', '', '', '', '', '0.1'),
               ('', '', '', '', '"GET /url/2 HTTP/1.1"', '', '', '', '', '', '', '', '0.2'),
               ('', '', '', '', '"GET /url/3 HTTP/1.1"', '', '', '', '', '', '', '', '0.3'),
               ('', '', '', '', '"GET /url/1 HTTP/1.1"', '', '', '', '', '', '', '', '0.4'),
               ('', '', '', '', '"GET /url/2 HTTP/1.1"', '', '', '', '', '', '', '', '0.3'),
               ('', '', '', '', '"GET /url/3 HTTP/1.1"', '', '', '', '', '', '', '', '0.2'),
               ('', '', '', '', '"GET /url/1 HTTP/1.1"', '', '', '', '', '', '', '', '0.21'),
               ('', '', '', '', '"GET /url/2 HTTP/1.1"', '', '', '', '', '', '', '', '0.32'),
               ('', '', '', '', '"GET /url/1 HTTP/1.1"', '', '', '', '', '', '', '', '0.11'),
               None
        ]

        stats = count_stats(log, err_perc=11)
        self.assertTrue(stats['ok'])
        self.assertEqual(len(stats['stats']), 3)
        self.assertDictEqual(stats['stats']['/url/1'], {
            'url': '/url/1', 'count': 4, 'time_sum': 0.82, 'time_max': 0.4, 'time_med': 0.16, 'count_perc': 44.444, 'time_perc': 38.318, 'time_avg': 0.205
        })
        self.assertDictEqual(stats['stats']['/url/2'], {
            'url': '/url/2', 'count': 3, 'time_sum': 0.82, 'time_max': 0.32, 'time_med': 0.3, 'count_perc': 33.333, 'time_perc': 38.318, 'time_avg': 0.273
        })
        self.assertDictEqual(stats['stats']['/url/3'], {
            'url': '/url/3', 'count': 2, 'time_sum': 0.5, 'time_max': 0.3, 'time_med': 0.25, 'count_perc': 22.222, 'time_perc': 23.364, 'time_avg': 0.25
        })

    def test_count_stats_error(self):
        log = [('', '', '', '', '"GET /url/1 HTTP/1.1"', '', '', '', '', '', '', '', '0.1'),
               ('', '', '', '', '"GET /url/2 HTTP/1.1"', '', '', '', '', '', '', '', '0.2'),
               ('', '', '', '', '"GET /url/3 HTTP/1.1"', '', '', '', '', '', '', '', '0.3'),
               ('', '', '', '', '"GET /url/1 HTTP/1.1"', '', '', '', '', '', '', '', '0.4'),
               ('', '', '', '', '"GET /url/2 HTTP/1.1"', '', '', '', '', '', '', '', '0.3'),
               ('', '', '', '', '"GET /url/3 HTTP/1.1"', '', '', '', '', '', '', '', '0.2'),
               ('', '', '', '', '"GET /url/1 HTTP/1.1"', '', '', '', '', '', '', '', '0.21'),
               ('', '', '', '', '"GET /url/2 HTTP/1.1"', '', '', '', '', '', '', '', '0.32'),
               ('', '', '', '', '"GET /url/1 HTTP/1.1"', '', '', '', '', '', '', '', '0.11'),
               None
        ]

        stats = count_stats(log, err_perc=1)
        self.assertFalse(stats['ok'])
        self.assertEqual(stats['err_perc'], 10)

    def test_render_report(self):
        stats = {
            '/url/1': {
                'url': '/url/1', 'count': 4, 'time_sum': 0.82, 'time_max': 0.4, 'time_med': 0.16, 'count_perc': 44.444, 'time_perc': 38.318, 'time_avg': 0.205
            },
            '/url/2': {
                'url': '/url/2', 'count': 3, 'time_sum': 0.82, 'time_max': 0.32, 'time_med': 0.3, 'count_perc': 33.333, 'time_perc': 38.318, 'time_avg': 0.273
            },
            '/url/3': {
                'url': '/url/3', 'count': 2, 'time_sum': 0.5, 'time_max': 0.3, 'time_med': 0.25, 'count_perc': 22.222, 'time_perc': 23.364, 'time_avg': 0.25
            }
        }

        report = render_report(stats, 2, '<html>$table_json;</html>')
        self.assertEqual(report, "<html>[{'url': '/url/1', 'count': 4, 'time_sum': 0.82, 'time_max': 0.4, 'time_med': 0.16, 'count_perc': 44.444, 'time_perc': 38.318, 'time_avg': 0.205}, {'url': '/url/2', 'count': 3, 'time_sum': 0.82, 'time_max': 0.32, 'time_med': 0.3, 'count_perc': 33.333, 'time_perc': 38.318, 'time_avg': 0.273}];</html>")

    def test_read_config_empty(self):
        config_path = path.join(self.test_path, 'config.ini')
        Path(config_path).touch()

        config_orig = {
            "REPORT_SIZE": 1000,
            "REPORT_DIR":  "./test",
            "LOG_DIR":     "./test",
            "LOG_FILE":    None
        }
        config_new = dict(config_orig)

        read_config(config_new, config_path)

        self.assertDictEqual(config_new, config_orig)

    def test_read_config(self):
        config_path = path.join(self.test_path, 'config.ini')
        with open(config_path, "w") as f:
            f.write('{"REPORT_DIR":  "./test-new", "UNKNOWN_ARG": 777}')

        config = {
            "REPORT_SIZE": 1000,
            "REPORT_DIR":  "./test",
            "LOG_DIR":     "./test",
            "LOG_FILE":    None
        }

        read_config(config, config_path)

        self.assertDictEqual(config, {
            "REPORT_SIZE": 1000,
            "REPORT_DIR":  "./test-new",
            "LOG_DIR":     "./test",
            "LOG_FILE":    None
        })


if __name__ == '__main__':
    unittest.main()
