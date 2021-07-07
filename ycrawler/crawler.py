#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import aiofiles
import aiohttp
import argparse
import asyncio
import itertools
import logging
import os

from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin


class Crawler(object):
    ROOT_URL = "https://news.ycombinator.com/"
    NEWS_COUNT = 30

    def __init__(self, storage_path, interval):
        self.storage_path = storage_path
        self.interval = interval
        self.loop = asyncio.get_event_loop()
        # Семафор для ограничения количества асинхронных скачиваний.
        self.sem = asyncio.Semaphore(10)

    def start(self):
        logging.info(f'Starting crawler')

        try:
            self.loop.run_until_complete(self._job())
        except asyncio.CancelledError:
            pass

    def stop(self):
        logging.info(f'Stopping crawler')
        self.loop.close()

    async def _job(self):
        """ Каждые `interval` секунд запускаем парсинг новостной страницы.
        """
        async with aiohttp.ClientSession() as session:
            while True:
                logging.info("Start crawling")

                await self._handle_link(
                    session, Crawler.ROOT_URL, self._parse_news_list
                )

                await asyncio.sleep(self.interval)

    async def _parse_news_list(self, session, response, html):
        """ Парсим страницу со списком новостей. """

        try:
            html = html.decode(response.charset or "utf-8")

            soup = BeautifulSoup(html, "html.parser")
            things = soup.find_all("tr", class_="athing")
            for thing in itertools.islice(things, Crawler.NEWS_COUNT):
                # У каждой новости есть идентификатор и ссылка.
                # Ссылка может быть относительной, если новость
                # на этом же сайте.
                id = thing["id"]
                link = thing.find("a", class_="storylink")["href"]
                if not urlparse(link).netloc:
                    link = urljoin(Crawler.ROOT_URL, link)

                # Скачиваем файл с новостью, если его еще нет на диске.
                news_path = self._get_news_path(id)
                if os.path.exists(news_path):
                    logging.debug(f"Skipping {id} news")
                else:
                    logging.info(f"Downloading {id} news")
                    asyncio.create_task(
                        self._handle_link(
                            session, link, self._save_file, path=news_path
                        )
                    )

                # Скачиваем страницу с комментариями.
                logging.info(f"Downloading comments for {id} news")
                comm_link = urljoin(Crawler.ROOT_URL, f"item?id={id}")
                asyncio.create_task(
                    self._handle_link(
                        session, comm_link, self._parse_comments, news_id=id
                    )
                )
        except Exception as e:
            logging.error(f"Cannot handle news list: {e}")

    async def _parse_comments(self, session, response, html, news_id):
        """ Парсим страницу со списком комментариев. """

        try:
            html = html.decode(response.charset or "utf-8")

            soup = BeautifulSoup(html, "html.parser")
            comments = soup.find_all("tr", class_=["athing", "comtr"])
            for comm in comments:
                comm_id = comm["id"]

                # Проверяем, скачан ли хотя бы один файл для этого
                # комментария. Если да, пропускаем комментарий.
                comm_path = self._get_comment_path(news_id, comm_id, 0)
                if os.path.exists(comm_path):
                    logging.debug(f"Skipping {news_id}-{comm_id} comment")
                    continue

                comm_a_tags = comm.find_all("a", rel=True)
                for count, a_tag in enumerate(comm_a_tags):
                    logging.info(
                        f"Downloading {news_id}-{comm_id} {count}'s links"
                    )
                    comm_file_path = self._get_comment_path(
                        news_id, comm_id, count
                    )
                    asyncio.create_task(
                        self._handle_link(
                            session, a_tag["href"],
                            self._save_file, path=comm_file_path
                        )
                    )
        except Exception as e:
            logging.error(f"Cannot handle comments page: {e}")

    async def _save_file(self, session, response, html, path):
        """ Получаем из запроса текст страницы и сохраняем его в файл `path`.
        """
        try:
            async with aiofiles.open(path, "wb") as out:
                await out.write(html)
                await out.flush()
                logging.debug(f"Saved {path}")
        except Exception as e:
            logging.error(f"Cannot save {path}: {e}")

    async def _handle_link(self, session, url, handler, **kwargs):
        """ Делает запрос по ссылке и передает `response`
            на обработку в `handler`. При ошибках повторяем
            запрос три раза.
        """
        html = None
        for _ in range(3):
            try:
                async with self.sem:
                    async with session.get(url) as response:
                        if response.ok:
                            html = await response.read()
                            break
                        logging.error(f"Cannot get {url}: {response.status}")
            except Exception as e:
                logging.error(f"Cannot get {url}: {e}")

            await asyncio.sleep(2)

        if html:
            logging.info(f"Downloaded {url}")
            asyncio.create_task(
                handler(session=session, response=response, html=html, **kwargs)
            )

    def _get_news_path(self, news_id):
        """ Возвращает путь до файла с новостью. """
        return os.path.join(self.storage_path, f"{news_id}.html")

    def _get_comment_path(self, news_id, comment_id, file_num):
        """ Возвращает путь до файла, упомянутого в комментарии к новости. """
        return os.path.join(
            self.storage_path,
            f"{news_id}-{comment_id}-{file_num}.html"
        )


if __name__ == '__main__':
    arg_parser = argparse.ArgumentParser(
        description='YCombinator News Crawler.'
    )
    arg_parser.add_argument(
        '-s', '--storage', required=True,
        help='Storage folder'
    )
    arg_parser.add_argument(
        '-t', '--interval', default=600, type=int,
        help='Crawling interval (600 seconds by default)'
    )
    arg_parser.add_argument("-l", "--log-level", help="Set the logging level",
                            default='INFO',
                            choices=[
                                'DEBUG', 'INFO', 'WARNING',
                                'ERROR', 'CRITICAL'])

    args = arg_parser.parse_args()

    storage_path = os.path.abspath(args.storage)
    if not os.path.exists(storage_path):
        os.makedirs(storage_path)

    logging.basicConfig(level=getattr(logging, args.log_level))

    crawler = Crawler(storage_path, args.interval)
    try:
        crawler.start()
    except KeyboardInterrupt:
        pass
    finally:
        crawler.stop()
