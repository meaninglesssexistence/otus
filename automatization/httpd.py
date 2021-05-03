# -*- coding: utf-8 -*-

import argparse
import asyncio
import logging
import os
import platform
from utils import get_http_code_status, get_http_timestamp, get_mime_type, get_uri_path


class HttpServer(object):
    def __init__(self, host, port, doc_root, workers_num):
        self.workers_num = workers_num
        self._queue = asyncio.Queue()
        self._loop = asyncio.get_event_loop()
        reuse_port = None if platform.system() == "Windows" else True
        self._server_coro = asyncio.start_server(self._handle_connection,
                                                 host=host, port=port,
                                                 reuse_port=reuse_port)
        self.doc_root = doc_root

    def start(self):
        self._loop.run_until_complete(self._start_workers())
        self._server = self._loop.run_until_complete(self._server_coro)
        logging.info(f'Listening on {self._server.sockets[0].getsockname()}')
        self._loop.run_forever()

    def stop(self):
        self._loop.run_until_complete(self._stop_workers())
        self._server.close()
        self._loop.run_until_complete(self._server.wait_closed())
        self._loop.close()

    async def _start_workers(self):
        self._workers = []
        for _ in range(self.workers_num):
            worker = asyncio.create_task(self._worker())
            self._workers.append(worker)

    async def _stop_workers(self):
        for worker in self._workers:
            worker.cancel()

    async def _worker(self):
        while True:
            (reader, writer) = await self._queue.get()

            request = await self._read_request(reader)

            if request:
                start_str = request[0].split()
                if len(start_str) >= 2:
                    rtype = start_str[0]
                    uri = get_uri_path(start_str[1])

                    self._handle_request(rtype, uri, writer)
                else:
                    logging.error(f'Invalid request format')
                    writer.write(self._response_header(400))
            else:
                logging.error(f'Empty request')
                writer.write(self._response_header(400))

            writer.close()
            self._queue.task_done()

    async def _handle_connection(self, reader, writer):
        peername = writer.get_extra_info('peername')
        logging.info('Accepted connection from {}'.format(peername))

        await self._queue.put((reader, writer))

    async def _read_request(self, reader):
        request = []
        # Read request line by line until an empty one.
        while True:
            try:
                data = await asyncio.wait_for(reader.readline(), timeout=10.0)
                data = data.decode("utf-8").rstrip()
                if not data:
                    break
                request.append(data)
            except Exception:
                return None

        return request

    def _handle_request(self, rtype, uri, writer):
        if rtype == "GET" or rtype == "HEAD":
            logging.info(f'Handle {rtype} {uri}')
            path = self._get_path(uri)
            if path:
                (_, ext) = os.path.splitext(path)
                mime_type = get_mime_type(ext)

                try:
                    with open(path, 'rb') as file:
                        content = file.read()
                except Exception:
                    logging.error(f'URI forbidden')
                    writer.write(self._response_header(403))
                    return

                writer.write(
                    self._response_header(200, mime_type, len(content)))
                writer.write('\r\n'.encode("utf-8"))

                if rtype == "GET":
                    writer.write(content)
            else:
                logging.error(f'URI not found')
                writer.write(self._response_header(404))
        else:
            logging.error(f'Unknown request {rtype} {uri}')
            writer.write(self._response_header(405))

    def _get_path(self, uri):
        path = os.path.join(self.doc_root, uri.lstrip('/'))

        if os.path.isdir(path):
            path = os.path.join(path, "index.html")

        if os.path.isfile(path):
            return path
        else:
            return None

    def _response_header(self, http_code, mime_type=None, content_length=None):
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
