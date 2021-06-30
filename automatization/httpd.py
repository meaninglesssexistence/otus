
#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import logging
import os
import signal
import socket

from multiprocessing import Pool
from utils import (get_http_code_status, get_http_timestamp,
                   get_mime_type, get_uri_path)


class HttpServer(object):
    def __init__(self, host, port, doc_root, workers_num):
        self.host = host
        self.port = port
        self.workers_num = workers_num
        self.doc_root = doc_root

    def start(self):
        self.pool = Pool(
                processes=self.workers_num,
                initializer=HttpServer._worker_init
        )
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.host, self.port))
        self.socket.listen(self.workers_num)

        logging.info(f'Start server on {self.socket.getsockname()}')

        while True:
            conn, addr = self.socket.accept()
            logging.info(f'Accept connection from {addr}')
            self.pool.apply_async(HttpServer._worker, (conn, self.doc_root))

    def stop(self):
        logging.info('Stop server')
        self.socket.close()
        self.pool.close()
        self.pool.join()

    @staticmethod
    def _worker_init():
        """ Отключаем обработку Ctrl-C в дочерних процессах.
            Нажатие перехватит главный процесс и завершит
            дочерние.
        """
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    @staticmethod
    def _worker(conn, doc_root):
        """ Получаем сокет для работы с клиентом. Читаем данные
            запроса, вытаскиваем из тип запроса и URL. Передаем
            обработку в _handle_request().
        """
        try:
            request = HttpServer._get_request(conn)
            if not request:
                logging.info('Unexpected socket close')
                return
            params = request[0].split()
            if len(params) != 3:
                logging.error(f'Invalid request format')
                conn.sendall(HttpServer._response_header(400))
                return
            rtype = params[0].decode('utf-8')
            uri = get_uri_path(params[1].decode('utf-8'))
            HttpServer._handle_request(rtype, uri, conn, doc_root)
        except Exception as ex:
            logging.exception(ex)
        finally:
            conn.shutdown(1)
            conn.close()

    @staticmethod
    def _get_request(conn):
        """ Читаем запрос построчно до пустой строки или EOF.
            Возвращаем запрос, как список строк.
        """
        request = [b'']
        while True:
            # TODO: timeout?
            buf = conn.recv(1024)
            if not buf:
                return []
            for line in buf.split(b'\n'):
                if not line:
                    continue
                if request[-1].endswith(b'\r'):
                    request.append(line)
                else:
                    request[-1] += line
            if request[-1] == b'\r':
                break
        return request

    def _handle_request(rtype, uri, conn, doc_root):
        """ Обработка запроса. Получаем путь до файла на диске,
            прорверяем его корректность. Возвращаем файл (GET)
            или информацию о нем (HEAD).
        """
        if rtype != "GET" and rtype != "HEAD":
            logging.error(f'Unknown request {rtype} {uri}')
            conn.sendall(HttpServer._response_header(405))
            return

        logging.info(f'Handle {rtype} {uri}')
        path = HttpServer._get_path(doc_root, uri)
        if not path:
            logging.error(f'URI not found')
            conn.sendall(HttpServer._response_header(404))
            return

        logging.info(f'Requested {path}')

        if not HttpServer._is_safe_path(doc_root, path):
            logging.error(f'URI forbidden')
            conn.sendall(HttpServer._response_header(403))
            return

        (_, ext) = os.path.splitext(path)
        mime_type = get_mime_type(ext)

        if rtype == "GET":
            try:
                with open(path, 'rb') as file:
                    content = file.read()
            except Exception:
                logging.error(f'URI forbidden')
                conn.sendall(HttpServer._response_header(403))
                return

            conn.sendall(
                    HttpServer._response_header(200, mime_type, len(content))
            )
            conn.sendall(content)
        else:
            content_len = 0
            try:
                content_len = os.path.getsize(path)
            except Exception:
                logging.error(f'URI forbidden')
                conn.sendall(HttpServer._response_header(403))
                return

            conn.sendall(
                    HttpServer._response_header(200, mime_type, content_len)
            )

    @staticmethod
    def _is_safe_path(doc_root, path):
        """ Проверяем, что путь не выходит за границы 'корневой'
            директории.
        """
        common_path = os.path.commonpath([doc_root, path])
        return common_path == doc_root

    @staticmethod
    def _get_path(doc_root, uri):
        """ Возвращаем путь до файла на диске, соответствующий
            переданному URI.
        """
        path = os.path.join(doc_root, uri.lstrip('/'))

        if os.path.isdir(path):
            path = os.path.join(path, "index.html")

        if os.path.isfile(path):
            return os.path.realpath(path)
        else:
            return None

    @staticmethod
    def _response_header(http_code, mime_type=None, content_length=None):
        """ Возвращаем строку - ответ сервера на запрос клиента. """
        response = (
            f"HTTP/1.1 {http_code} {get_http_code_status(http_code)}\r\n"
            f"Date: {get_http_timestamp()}\r\n"
            f"Server: Goga\r\n"
            f"Connection: close\r\n"
        )

        if mime_type:
            response += "Content-Type: {}\r\n".format(mime_type)
        if content_length:
            response += "Content-Length: {}\r\n".format(content_length)
        else:
            response += "Content-Length: 0\r\n"
        response += "\r\n"

        return response.encode("utf-8")


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

    logging.basicConfig(level=getattr(logging, args.log_level))

    server = HttpServer('127.0.0.1', args.port, doc_root, args.workers)
    try:
        server.start()
    except KeyboardInterrupt:
        pass
    finally:
        server.stop()
