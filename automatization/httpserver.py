#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import signal
import socket

from multiprocessing import Pool
from utils import get_http_code_status, get_http_timestamp


class HttpError(Exception):
    pass


class BadRequest(HttpError):
    code = 400


class Forbidden(HttpError):
    code = 403


class NotFound(HttpError):
    code = 404


class MethodNotAllowed(HttpError):
    code = 405


class HttpRequest(object):
    """ Обработчик конкретного клиентского запроса.
        Позволяет считать данные запроса, распарсить
        параметры запроса и заголовки, отправить ответ.
    """

    def __init__(self, socket):
        self.socket = socket
        self.headers = []
        self.content = None
        self.method = None
        self.uri = None

    def close(self):
        """ Завершаем соединение, закрывая сокет.
        """
        self.socket.shutdown(1)
        self.socket.close()

    def read(self):
        """ Читаем данные запроса. По результату успешного чтения
            инициализируем:
            * method - метод запроса
            * uri - запрашиваемый URI
            * headers - словарь заголовков
            * content - опциональные данные запроса
        """
        data = b''
        headers_list = []
        while True:
            buf = self.socket.recv(1024)
            if not buf:
                break

            data += buf

            # Считываем данные из сокета, пока не обнаружим
            # пустую строку. Все, что до нее, это заголовки.
            # После нее - опциональные данные запроса.
            delim_pos = data.find(b'\r\n\r\n')
            if delim_pos != -1:
                headers_list = data[:delim_pos].split(b'\r\n')
                self.content = data[delim_pos+4:]
                break

        if not headers_list:
            raise BadRequest

        # Парсим метод и URI запроса.
        params = headers_list.pop(0).split()
        if len(params) != 3:
            raise BadRequest

        self.method = params[0].decode('utf-8')
        self.uri = params[1].decode('utf-8')

        # Превращаем список строк с заголовками в словарь:
        # заголовок -> значение.
        self.headers = dict(
            map(
                lambda x: x.strip(),
                x.decode('utf-8').split(':')
            ) for x in headers_list
        )

        # Дочитываем из сокета опциональные данные запроса,
        # если есть заголовок Content-Length.
        content_len = self.headers.get('Content-Length')
        if content_len:
            content_len = int(content_len)
            self.content += self.socket.recv(content_len)

    def response(self, code, custom_headers=None, content=None):
        """ Посылаем ответ на запрос с опциональными дополнительными
            заголовками и данными.
        """
        headers = {
            "Date": get_http_timestamp(),
            "Server": "Goga",
            "Connection": "close"
        }
        if custom_headers:
            headers.update(custom_headers)

        headers_str = f"HTTP/1.1 {code} {get_http_code_status(code)}\r\n"
        headers_str += '\r\n'.join(
            map(lambda x: f"{x[0]}: {x[1]}", headers.items())
        )
        headers_str += '\r\n\r\n'

        self.socket.sendall(headers_str.encode("utf-8"))
        if content:
            self.socket.sendall(content)


class HttpServer(object):
    """ HTTP Server обрабатывающий запросы с использованием
        пула процессов. Функция - обработчик запроса передается
        в конструктор через параметр handler. Сервер принимает
        подключение, создает экземпляр HttpRequest и вызывает
        функцию - обработчик, передавая ей HttpRequest.
    """

    def __init__(self, host, port, doc_root, workers_num, log_level, handler):
        self.host = host
        self.port = port
        self.workers_num = workers_num
        self.doc_root = doc_root
        self.log_level = log_level
        self.handler = handler

    def start(self):
        """ Запускаем сервер, инициализируем пул процессов и
            принимающий запросы сокет.
        """
        self.pool = Pool(
                processes=self.workers_num,
                initializer=HttpServer.worker_init
        )
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.bind((self.host, self.port))
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.listen(self.workers_num)

        logging.info(f'Start server on {self.socket.getsockname()}')

        while True:
            conn, addr = self.socket.accept()
            logging.info(f'Accept connection from {addr}')
            self.pool.apply_async(
                HttpServer.worker,
                (conn, self.handler, self.doc_root, self.log_level)
            )

    def stop(self):
        """ Останавливаем сервер, закрываем сокет, дожидаемся завершения
            процессов из пула.
        """
        logging.info('Stop server')
        self.socket.close()
        self.pool.close()
        self.pool.join()

    @staticmethod
    def worker_init():
        """ Отключаем обработку Ctrl-C в дочерних процессах.
            Нажатие перехватит главный процесс и завершит
            дочерние.
        """
        signal.signal(signal.SIGINT, signal.SIG_IGN)

    @staticmethod
    def worker(conn, handler, doc_root, log_level):
        """ Получаем сокет для работы с клиентом. Создаем экземпляр
            HttpRequest и вызываем обработчик запроса.
        """
        logging.basicConfig(level=log_level)

        request = HttpRequest(conn)
        try:
            handler(request, doc_root)
        except HttpError as ex:
            logging.info(f"Response {ex.code} {get_http_code_status(ex.code)}")
            request.response(ex.code)
        except Exception as ex:
            logging.exception(ex)
            request.response(500)
        finally:
            request.close()
