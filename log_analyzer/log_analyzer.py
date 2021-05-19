#!/usr/bin/env python
# -*- coding: utf-8 -*-


import gzip
import os
import argparse
import collections
import gzip
import re
import datetime
import statistics
import string
import json
import logging
import copy


config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR":  "./test",
    "LOG_DIR":     "./test",
    "LOG_FILE":    None
}

REGEX = re.compile(
    r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|-) ([0-9a-zA-Z]+|-)  (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|-) (\[.+]|-) (\"[A-Z]{3,7} .+ .+\") (\d{3}|-) (\d+|-) (\".+\") (\".+\") (\".+\") (\".+\") (\".+\") (\d+\.\d+|-)", re.DOTALL)

# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';


logFileTuple = collections.namedtuple("log", ["path", "date", "is_gz"])


def find_log(path):
    log_file = None
    files = os.scandir(path)
    file_prefix = "nginx-access-ui.log-"
    for elem in files:
        if not elem.is_file() or not elem.name.startswith(file_prefix):
            continue
        is_gz = False
        date = elem.name[len(file_prefix):]
        if date.endswith(".gz"):
            is_gz = True
            date = date[:-len(".gz")]

        if len(date) == 8:
            try:
                date = datetime.datetime.strptime(date, "%Y%m%d").date()
            except:
                continue
            if not log_file or date > log_file.date:
                log_file = logFileTuple(elem.path, date, is_gz)

    return log_file


def report_exists(path, date):
    return os.path.isfile(os.path.join(path, f"report-{date.strftime('%Y.%m.%d')}.html"))


def parse_log(log):
    opener = open if not log.is_gz else gzip.open

    with opener(log.path, "rt") as file:
        for line in file:
            if not line:
                continue

            line = line.rstrip("\n")
            parsed_line = REGEX.match(line)
            if parsed_line:
                yield parsed_line.groups()
            else:
                logging.debug(f"Could not parse '{line}'")
                yield None


def count_stats(log, err_perc):
    stats = {}
    requests_count = 0
    requests_time = 0
    err_count = 0

    for report in log:
        if not report:
            err_count += 1
            continue

        url = report[4]
        url = url.split()[1]
        time = float(report[12])

        requests_count += 1
        requests_time += time

        if not url in stats:
            stats[url] = {"url":      url,
                          "count":    1,
                          "time_sum": time,
                          "time_max": time,
                          "time_med": [time]}
        else:
            stats[url]["count"] += 1
            stats[url]["time_sum"] += time
            if time > stats[url]["time_max"]:
                stats[url]["time_max"] = time
            stats[url]["time_med"].append(time)

    actual_err_perc = 100 / ((err_count + requests_count) / err_count)
    if actual_err_perc >= err_perc:
        msg = f"There is more than {actual_err_perc}% of errors while parsing the log"
        logging.info(msg)
        return

    for url_stat in stats.values():
        url_stat["time_sum"] = round(url_stat["time_sum"], 3)
        url_stat["count_perc"] = round(
            100 / (requests_count / url_stat["count"]), 3)

        if url_stat["time_sum"] > 0:
            url_stat["time_perc"] = round(
                100 / (requests_time / url_stat["time_sum"]), 3)
        else:
            url_stat["time_perc"] = 0

        url_stat["time_avg"] = round(
            url_stat["time_sum"] / url_stat["count"], 3)
        url_stat["time_med"] = round(statistics.median(url_stat["time_med"]), 3)

    return stats


def save_report(log, max_entries, report_path):
    with open(os.path.join(os.path.dirname(os.path.realpath(__file__)), "template.html")) as file:
        log = sorted(log.values(),
                     key=lambda value: value["time_sum"],
                     reverse=True)[:max_entries]
        report = string.Template(str(file.read())).safe_substitute(table_json=log)
        with open(report_path, "w") as report_file:
            report_file.write(report)


def read_config(config, new_config):
    with new_config as file:
        config.update(json.load(file))
        return config


def main(config):
    parser = argparse.ArgumentParser()
    parser.add_argument("-c", "--config", type=argparse.FileType())

    new_config = parser.parse_args().config
    if new_config:
        try:
            config = read_config(copy.deepcopy(config), new_config)
        except Exception as err:
            print("Cant parse config")
            raise err

    logging.basicConfig(filename=config["LOG_FILE"],
                        format="[%(asctime)s] %(levelname).1s %(message)s",
                        datefmt="%Y.%m.%d %H:%M:%S",
                        level=logging.DEBUG)

    try:
        log = find_log(os.path.realpath(config["LOG_DIR"]))
        if not log:
            logging.info('Could not find any logs')
            return

        report_dir = os.path.realpath(config["REPORT_DIR"])
        if report_exists(report_dir, log.date):
            logging.info(f'Report for {log.date} exists')
        else:
            stats = count_stats(parse_log(log), err_perc=50)
            if stats:
                report_date = log.date.strftime('%Y.%m.%d')
                report_file = os.path.join(report_dir, f"report-{report_date}.html")
                report_size = config["REPORT_SIZE"]
                save_report(stats, report_size, report_file)

    except Exception as err:
        logging.exception(err)


if __name__ == "__main__":
    main(config)
