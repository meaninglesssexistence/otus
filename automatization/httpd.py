#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os

from httpserver import HttpServer, Forbidden, MethodNotAllowed, NotFound
from multiprocessing import Pool
from multiprocessing_logging import install_mp_handler
from utils import get_mime_type, strip_uri_path


def get_path(doc_root, uri):
    """ Возвращаем путь до файла на диске, соответствующий
        переданному URI. Полагаемся на то, что doc_root
        уже приведен к абсолютному виду. Если запрошенный путь
        выходит за границы doc_root, считаем что такого файла нет.
    """
    path = os.path.join(doc_root, uri.lstrip('/'))

    common_path = os.path.commonpath([doc_root, path])
    if common_path != doc_root:
        return None

    if os.path.isdir(path):
        path = os.path.join(path, "index.html")

    if not os.path.isfile(path):
        return None

    return path


def handle_request(request, doc_root):
    """ Читаем запрос, получаем HTTP метод и запрошенный путь
        до файла на диске. Отправляем ответ на запрос.
    """
    request.read()

    method = request.method
    uri = strip_uri_path(request.uri)

    if method not in ["GET", "HEAD"]:
        raise MethodNotAllowed

    logging.info(f'Handle {method} {uri}')
    path = get_path(doc_root, uri)
    if not path:
        raise NotFound

    logging.info(f'Requested {path}')

    (_, ext) = os.path.splitext(path)
    mime_type = get_mime_type(ext)

    content = None
    content_len = 0
    if method == "GET":
        try:
            with open(path, 'rb') as file:
                content = file.read()
            content_len = len(content)
        except Exception:
            raise Forbidden
    else:
        try:
            content_len = os.path.getsize(path)
        except Exception:
            raise Forbidden

    request.response(
        200,
        {"Content-Type": mime_type, "Content-Length": content_len},
        content
    )


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(description='Simple HTTP Server.')
    arg_parser.add_argument('-r', '--doc-root', help='documents root')
    arg_parser.add_argument('-w', '--workers', help='number of workers',
                            type=int, default=5)
    arg_parser.add_argument('-p', '--port', help='port number',
                            type=int, default=80)
    arg_parser.add_argument("-l", "--log-level", help="Set the logging level",
                            default='INFO',
                            choices=[
                                'DEBUG', 'INFO', 'WARNING',
                                'ERROR', 'CRITICAL'])

    args = arg_parser.parse_args()

    if args.doc_root:
        doc_root = os.path.abspath(args.doc_root)
    else:
        doc_root = os.getcwd()

    log_level = getattr(logging, args.log_level)
    logging.basicConfig(level=getattr(logging, args.log_level))
    install_mp_handler()

    server = HttpServer(
        '127.0.0.1', args.port,
        doc_root, args.workers, log_level,
        handle_request
    )
    try:
        server.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
