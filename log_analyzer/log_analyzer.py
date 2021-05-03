#!/usr/bin/env python
# -*- coding: utf-8 -*-


from os.path import dirname, isfile, join, realpath
from argparse import ArgumentParser, FileType
from collections import namedtuple
from gzip import open as gzopen
from re import I, compile, DOTALL
from datetime import datetime
from statistics import median
from string import Template
from os import scandir
from json import loads as json_loads
import logging


config = {
    "REPORT_SIZE": 1000,
    "REPORT_DIR":  "./test",
    "LOG_DIR":     "./test",
    "LOG_FILE":    None
}

REGEX = compile(
    r"(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|-) ([0-9a-zA-Z]+|-)  (\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}|-) (\[.+]|-) (\"[A-Z]{3,7} .+ .+\") (\d{3}|-) (\d+|-) (\".+\") (\".+\") (\".+\") (\".+\") (\".+\") (\d+\.\d+|-)", DOTALL)

# log_format ui_short '$remote_addr  $remote_user $http_x_real_ip [$time_local] "$request" '
#                     '$status $body_bytes_sent "$http_referer" '
#                     '"$http_user_agent" "$http_x_forwarded_for" "$http_X_REQUEST_ID" "$http_X_RB_USER" '
#                     '$request_time';


logFileTuple = namedtuple("log", ["path", "date", "is_gz"])


def find_log(path):
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
                    log_file = logFileTuple(elem.path, date, is_gz)

    return log_file


def report_exists(path, date):
    return isfile(join(path, f"report-{date.strftime('%Y.%m.%d')}.html"))


def parse_log(log):
    opener = open if not log.is_gz else gzopen

    with opener(log.path, "rt") as file:
        for line in file:
            if line:
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


def save_report(log, max_entries, report_path):
    with open(join(dirname(realpath(__file__)), "template.html")) as file:
        log = sorted(log.values(),
                     key=lambda value: value["time_sum"],
                     reverse=True)[:max_entries]
        report = Template(str(file.read())).safe_substitute(table_json=log)
        with open(report_path, "w") as report_file:
            report_file.write(report)


def read_config(config, new_config):
    with new_config as file:
        config_str = file.read()
        if config_str:
            user_config = json_loads(config_str)
            for key in config.keys():
                if key in user_config.keys():
                    config.update(user_config)
        else:
            logging.info("Config file is empty")


def main(config):
    parser = ArgumentParser()
    parser.add_argument("-c", "--config", type=FileType())

    new_config = parser.parse_args().config
    if new_config:
        try:
            read_config(config, new_config)
        except Exception as err:
            print("Cant parse config")
            raise err

    logging.basicConfig(filename=config["LOG_FILE"],
                        format="[%(asctime)s] %(levelname).1s %(message)s",
                        datefmt="%Y.%m.%d %H:%M:%S",
                        level=logging.DEBUG)

    try:
        log = find_log(realpath(config["LOG_DIR"]))
        if log:
            report_dir = realpath(config["REPORT_DIR"])
            if report_exists(report_dir, log.date):
                logging.info(f'Report for {log.date} exists')
            else:
                stats = count_stats(parse_log(log), err_perc=50)
                if stats["ok"]:
                    report_date = log.date.strftime('%Y.%m.%d')
                    report_file = join(report_dir, f"report-{report_date}.html")
                    report_size = config["REPORT_SIZE"]
                    save_report(stats["stats"], report_size, report_file)
                else:
                    msg = f"There is more than {stats['err_perc']}% of errors while parsing the log"
                    logging.info(msg)
        else:
            logging.info('Could not find any logs')


    except Exception as err:
        logging.exception(err)


if __name__ == "__main__":
    main(config)
