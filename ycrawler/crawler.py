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
from collections import namedtuple
from urllib.parse import urlparse, urljoin


ROOT_URL = "https://news.ycombinator.com/"
NEWS_COUNT = 30


Context = namedtuple(
    "Context",
    "session request_retries retries_sleep storage_path"
)


def parse_news_list_page(html):
    """ Парсим страницу со списком новостей.
        Возвращаем кортежи (id новости, ссылка на новость).
    """

    soup = BeautifulSoup(html, "html.parser")
    for thing in soup.find_all("tr", class_="athing"):
        # У каждой новости есть идентификатор и ссылка.
        # Ссылка может быть относительной, если новость
        # на этом же сайте.
        id = thing["id"]
        link = thing.find("a", class_="storylink")["href"]
        if not urlparse(link).netloc:
            link = urljoin(ROOT_URL, link)

        yield (id, link)


def parse_comments_page(html):
    """ Парсим страницу со списком комментариев.
        Возвращаем кортежи (id комментария, [ссылки в комментарии]).
    """

    soup = BeautifulSoup(html, "html.parser")
    for comm in soup.find_all("tr", class_=["athing", "comtr"]):
        comm_id = comm["id"]

        comm_a_tags = comm.find_all("a", rel=True)
        yield (comm_id, [a_tag["href"] for a_tag in comm_a_tags])


async def request_link(ctx, url, handler, **kwargs):
    """ Делает запрос по ссылке `url` и передает `response` на асинхронную
        обработку в `handler` вместе с аргументами из `kwargs`. При ошибках
        повторяем запрос `ctx.request_retries` раз с интервалами
        в `ctx.retries_sleep` секунд.
    """
    html = None
    for _ in range(ctx.request_retries):
        try:
            async with ctx.session.get(url) as response:
                if response.ok:
                    html = await response.read()
                    break
                logging.error(f"Cannot get {url}: {response.status}")
        except Exception as e:
            logging.error(f"Cannot get {url}: {e}")

        await asyncio.sleep(ctx.retries_sleep)

    if html:
        logging.info(f"Downloaded {url}")
        asyncio.create_task(
            handler(ctx=ctx, response=response, html=html, **kwargs)
        )


def get_news_file_path(storage_path, news_id):
    """ Возвращает путь до файла с новостью. """
    return os.path.join(storage_path, f"{news_id}.html")


def get_comment_file_path(storage_path, news_id, comment_id, file_num):
    """ Возвращает путь до файла, упомянутого в комментарии к новости. """
    return os.path.join(storage_path, f"{news_id}-{comment_id}-{file_num}.html")


async def save_file(ctx, response, html, path):
    """ Сохраняем содержимое `html` в файл `path`."""
    try:
        async with aiofiles.open(path, "wb") as out:
            await out.write(html)
            await out.flush()
            logging.debug(f"Saved {path}")
    except Exception as e:
        logging.error(f"Cannot save {path}: {e}")


async def handle_comments(ctx, response, html, news_id):
    """ Обрабатываем страницу со списком комментариев.
        Парсим, скачиваем файлы, упомянутые в комментариях.
    """

    try:
        html = html.decode(response.charset or "utf-8")

        for comm_id, links in parse_comments_page(html):
            # Проверяем, скачан ли хотя бы один файл для этого
            # комментария. Если да, пропускаем комментарий.
            comm_path = get_comment_file_path(
                ctx.storage_path, news_id, comm_id, 0
            )
            if os.path.exists(comm_path):
                logging.debug(f"Skipping {news_id}-{comm_id} comment")
                continue

            for count, link in enumerate(links):
                logging.info(
                    f"Downloading {news_id}-{comm_id} {count}'s links"
                )
                comm_file_path = get_comment_file_path(
                    ctx.storage_path, news_id, comm_id, count
                )
                asyncio.create_task(
                    request_link(ctx, link, save_file, path=comm_file_path)
                )
    except Exception as e:
        logging.error(f"Cannot handle comments page: {e}")


async def handle_news_list(ctx, response, html):
    """ Обрабатываем страницу со списком новостей.
        Парсим, скачиваем новость, обрабатываем список комментариев.
    """

    try:
        html = html.decode(response.charset or "utf-8")

        news = parse_news_list_page(html)
        for id, link in itertools.islice(news, NEWS_COUNT):
            # Скачиваем файл с новостью, если его еще нет на диске.
            news_path = get_news_file_path(ctx.storage_path, id)
            if os.path.exists(news_path):
                logging.debug(f"Skipping {id} news")
            else:
                logging.info(f"Downloading {id} news")
                asyncio.create_task(
                    request_link(ctx, link, save_file, path=news_path)
                )

            # Скачиваем страницу с комментариями.
            logging.info(f"Downloading comments for {id} news")
            comm_link = urljoin(ROOT_URL, f"item?id={id}")
            asyncio.create_task(
                request_link(ctx, comm_link, handle_comments, news_id=id)
            )
    except Exception as e:
        logging.error(f"Cannot handle news list: {e}")


async def crawler_job(connections, interval, request_retries, retries_sleep, storage_path):
    """ Каждые `interval` секунд запускаем парсинг новостной страницы."""

    conn = aiohttp.TCPConnector(limit=connections)
    async with aiohttp.ClientSession(connector=conn) as session:
        ctx = Context(session, request_retries, retries_sleep, storage_path)
        while True:
            logging.info("Start crawling")

            await request_link(ctx, ROOT_URL, handle_news_list)

            await asyncio.sleep(interval)


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
    arg_parser.add_argument(
        '-p', '--connections', default=10, type=int,
        help='Number of simultaneously opened connections (10 by default)'
    )
    arg_parser.add_argument(
        '-r', '--request-retries', default=3, type=int,
        help='Number of HTTP request retries (3 by default)'
    )
    arg_parser.add_argument(
        '-w', '--retries-sleep', default=2, type=int,
        help='Number of seconds to sleep between HTTP request retries (2 seconds by default)'
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

    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(
            crawler_job(
                args.connections, args.interval,
                args.request_retries, args.retries_sleep,
                storage_path
        ))
    except KeyboardInterrupt:
        pass
    except asyncio.CancelledError:
        pass
    finally:
        loop.close()
