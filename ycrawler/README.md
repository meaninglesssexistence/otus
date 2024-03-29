﻿# Ycrawler

Задание: написать асинхронный краулер для новостного сайта
[news.ycombinator.com](https://news.ycombinator.com)

Цель задания: поближе познакомиться с асинхронным программированием, получить
опыт написания и отладки асинхронных программ.

Критерии успеха: задание обязательно, критерием успеха является работающий
согласно заданию код, для которого проверено соответствие pep8, написана
документация с примерами запуска, в README, например. Далее успешность
определяется code review.

## Описание

* Программа скачивает 30 новостей с корневой страницы news.ycombinator.com.
  Каждая новость имеет идентификатор. Проверяется наличие файла с именем
  `<id-новости>.html`. Если файла нет, скачивается файл по новостной ссылке.

* Независимо от наличия файла с самой новостью, скачивается файл с
  комментариями. Каждый комментарий имеет свой идентификатор и может содержать
  несколько сылок. Каждая ссылка сохраняется в файле с именем
  `<id-новости>-<id-комментария>-<порядковый номер ссылки в комментарии>.html`.
  Если для комментария уже скачан хотя бы один файл, этот комментарий
  пропускается. В противном случае скачиваются файлы по всем ссылкам в
  комментарии.

## Параметры запуска

```
usage: crawler.py [-h] -s STORAGE [-t INTERVAL] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]

YCombinator News Crawler.

optional arguments:
  -h, --help            show this help message and exit
  -s STORAGE, --storage STORAGE
                        Storage folder
  -t INTERVAL, --interval INTERVAL
                        Crawling interval (600 seconds by default)
  -p CONNECTIONS, --connections CONNECTIONS
                        Number of simultaneously opened connections (10 by default)
  -r REQUEST_RETRIES, --request-retries REQUEST_RETRIES
                        Number of HTTP request retries (3 by default)
  -w RETRIES_SLEEP, --retries-sleep RETRIES_SLEEP
                        Number of seconds to sleep between HTTP request retries (2 seconds by default)
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set the logging level
```

## Пример запуска

Сохраняем файлы в папке `storage`. Запускаем скачивание каждые 600 секунд.
```
$ ./crawler.py -s storage -t 600
```
