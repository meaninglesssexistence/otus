#!/usr/bin/env python
# -*- coding: utf-8 -*-


from os.path import dirname, isfile, join, realpath
from getopt import getopt, GetoptError
from collections import namedtuple
from gzip import open as gzopen
from re import compile, DOTALL
from datetime import datetime
from statistics import median
from string import Template
from sys import argv, exit
from os import scandir
from json import loads as json_loads
import logging


config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR":  "./test",
    "LOG_DIR":     "./test",
    "LOG_FILE":    None
}


# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';


def find_log(path):
    log_file_tuple = namedtuple("log", ["path", "date", "is_gz"])
    log_file = None

    files = scandir(path)
    file_prefix = "nginx-access-ui.log-"
    for elem in files:
        if elem.is_file() and elem.name.startswith(file_prefix):
            is_gz = False
            date = elem.name[len(file_prefix):]
            if date.endswith(".gz"):
                is_gz = True
                date = date[:-len(".gz")]

            if len(date) == 8:
                try:
                    date = datetime.strptime(date, "%Y%m%d").date()
                except:
                    continue
                if not log_file or date > log_file.date:
                    log_file = log_file_tuple(elem.path, date, is_gz)

    return log_file


def report_exists(path, date):
    return isfile(join(path, f"report-{date.strftime('%Y.%m.%d')}.html"))


def parse_log(path, is_gz):
    if is_gz:
        _open = gzopen
    else:
        _open = open

    with _open(path, "rt") as file:
        regex = compile(
            r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|-) ([0-9a-zA-Z]+|-)  (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|-) (\[.+]|-) (\"[A-Z]{3,7} .+ .+\") (\d{3}|-) (\d+|-) (\".+\") (\".+\") (\".+\") (\".+\") (\".+\") (\d+\.\d+|-)", DOTALL)
        for line in file:
            if line:
                line = line.rstrip("\n")
                parsed_line = regex.match(line)
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
        if report:
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
        else:
            err_count += 1

    actual_err_perc = 100 / ((err_count + requests_count) / err_count)
    if actual_err_perc >= err_perc:
        return {"ok":       False,
                "err_perc": actual_err_perc}

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
        url_stat["time_med"] = round(median(url_stat["time_med"]), 3)

    return {"ok":    True,
            "stats": stats}


def render_report(log, max_entries, templ):
    table = sorted(log.values(), key=lambda value: value["time_sum"], reverse=True)

    return Template(templ).safe_substitute(table_json=table[:max_entries])


def save_report(log, max_entries, report_path):
    with open(join(dirname(realpath(__file__)), "template.html")) as file:
        report = render_report(log, max_entries, str(file.read()))
        with open(report_path, "w") as report_file:
            report_file.write(report)


def make_log_report(report_size, report_dir, log_dir):
    log = find_log(log_dir)
    if log:
        if report_exists(report_dir, log.date):
            logging.info(f'Report for {log.date} exists')
        else:
            stats = count_stats(parse_log(log.path, log.is_gz), err_perc=50)
            if stats["ok"]:
                report_file = join(
                    report_dir, f"report-{log.date.strftime('%Y.%m.%d')}.html")
                save_report(stats["stats"], report_size, report_file)
            else:
                logging.info(
                    f"There is more than {stats['err_perc']}% of errors while parsing the log")
    else:
        logging.info('Could not find any logs')


def read_config(config, config_path):
    with open(config_path, "r") as file:
        config_str = file.read()
        if config_str:
            user_config = json_loads(config_str)
            for key in config.keys():
                if key in user_config.keys():
                    config[key] = user_config[key]
        else:
            logging.info("Config file is empty")


def main(argv, config):
    try:
        opts, _ = getopt(argv, "c:", ["config="])
    except GetoptError:
        print("Cant parse arguments")
        exit(2)

    for opt, val in opts:
        if opt in ("-c", "--config"):
            try:
                read_config(config, realpath(val))
            except Exception as err:
                print("Cant parse config")
                raise err

    logging.basicConfig(filename=config["LOG_FILE"],
                        format="[%(asctime)s] %(levelname).1s %(message)s",
                        datefmt="%Y.%m.%d %H:%M:%S",
                        level=logging.DEBUG)

    try:
        make_log_report(config["REPORT_SIZE"],
                        realpath(config["REPORT_DIR"]),
                        realpath(config["LOG_DIR"]))
    except Exception as err:
        logging.exception(err)


if __name__ == "__main__":
    main(argv[1:], config)
