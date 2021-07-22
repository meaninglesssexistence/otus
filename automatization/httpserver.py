#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import os
import signal
import socket

from datetime import datetime
from email.utils import formatdate
from http import HTTPStatus
from multiprocessing import Pool
from time import mktime


class HttpError(Exception):
    def __init__(self, httpStatus):
        self.httpStatus = httpStatus


def read_request(socket):
    """ Читаем данные запроса. Возвращаем кортеж:
        * requets-line
        * message-header - как массив строк
    """
    data = b''
    headers_list = []
    while True:
        buf = socket.recv(1024)
        if not buf:
            break

        data += buf

        # Считываем данные из сокета, пока не обнаружим
        # пустую строку. Все, что до нее, это заголовки.
        # После нее - опциональные данные запроса.
        delim_pos = data.find(b'\r\n\r\n')
        if delim_pos != -1:
            headers_list = data[:delim_pos].split(b'\r\n')
            break

    if not headers_list:
        raise HttpError(HTTPStatus.BAD_REQUEST)

    return (
        headers_list[0],
        headers_list[1:]
    )


def parse_request(request_line, headers_list):
    """ Парсим данные запроса. Возвращаем кортеж:
        * method - метод запроса
        * uri - запрашиваемый URI
        * headers - словарь заголовков
    """

    # Парсим метод и URI запроса.
    params = request_line.split()
    if len(params) != 3:
        raise HttpError(HTTPStatus.BAD_REQUEST)

    method = params[0].decode('utf-8')
    uri = params[1].decode('utf-8')

    # Превращаем список строк с заголовками в словарь:
    # заголовок -> значение.
    headers = dict(
        map(
            lambda x: x.strip(),
            x.decode('utf-8').split(':')
        ) for x in headers_list
    )

    return (method, uri, headers)


def get_http_timestamp():
    """ Возвращаем текущее время, отформатированное по RFC 1123. """
    return formatdate(timeval=mktime(datetime.now().timetuple()),
                      localtime=False, usegmt=True)


def send_response(socket, httpStatus, custom_headers=None, content=None):
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

    headers_str = f"HTTP/1.1 {httpStatus.value} {httpStatus.phrase}\r\n"
    headers_str += '\r\n'.join(
        map(lambda x: f"{x[0]}: {x[1]}", headers.items())
    )
    headers_str += '\r\n\r\n'

    socket.sendall(headers_str.encode("utf-8"))
    if content:
        socket.sendall(content)


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
    def worker(socket, handler, doc_root, log_level):
        """ Получаем сокет для работы с клиентом. Читаем данные запроса,
            парсим их и передаем результаты в обработчик `handler`.
        """
        logging.basicConfig(level=log_level)

        try:
            request_line, headers_list = read_request(socket)
            method, uri, headers = parse_request(request_line, headers_list)
            handler(socket, method, uri, headers, doc_root)
        except HttpError as ex:
            logging.info(
                f"Response {ex.httpStatus.value} {ex.httpStatus.phrase}"
            )
            send_response(socket, ex.httpStatus)
        except Exception as ex:
            logging.exception(ex)
            send_response(socket, HTTPStatus.INTERNAL_SERVER_ERROR)
        finally:
            socket.shutdown(1)
            socket.close()
