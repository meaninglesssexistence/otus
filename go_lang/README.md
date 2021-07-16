# MemcLoad v2

Задание: нужно переписать Python версию `memc_load.py` на Go.
Программа по-прежнему парсит и заливает в мемкеш поминутную выгрузку
логов трекера установленных приложений. Ключом является тип и идентификатор
устройства через двоеточие, значением являет protobuf сообщение

## Описание

Программа последовательно распаковывает, читает и парсит указанные файлы
с логами. Распаршеный результат передается в одну из четырех go-роутин
через соответствующий канал. Каждая из go-роутин ответственна за сериализацию
и пересылку в memcache данных для определенного типа устройств: 
_idfa, gaid, adid, dvid._ Для непосредственной отправки сериализованных данных
memcache-серверу запускается отдельная go-роутина. По одной на каждый сервер.
Если эта go-роутина не занята, сериализованный пакет передается в нее через
канал. Если занята - данные помещаются в очередь.

## Параметры программы

```
$ ./memc_load.exe --help
Usage of memc_load.exe:
  -adid string
        ADID MemCache address (default "127.0.0.1:33015")
  -dry
        dry run
  -dvid string
        DVID MemCache address (default "127.0.0.1:33016")
  -gaid string
        GAID MemCache address (default "127.0.0.1:33014")
  -idfa string
        IDFA MemCache address (default "127.0.0.1:33013")
  -l string
        log file name
  -log string
        log file name
  -pattern string
        glob for input file (default "/data/appsinstalled/*.tsv.gz")
  -t    test parsing
  -test
        test parsing
```

## Варианты запуска

Для инициализации проекта, сборки и запуска тестов можно использовать `Makefile`

* Инициализация проекта, скачивание зависимостей: `make init`

* Сборка проекта: `make build`

* Запуск программы в тестовом режиме: `make test-soft`

* Запуск программы с обработкой файлов: `make startsvc test-hard`

## Пример запуска

```
$ make startsvc test-hard
go build
./memc_load -pattern *.tsv.gz
2021/07/15 22:37:26 Processing 20170929000000.tsv.gz
2021/07/15 22:38:19 Processing 20170929000100.tsv.gz
2021/07/15 22:41:02 Acceptable error rate (0). Successfull load
2021/07/15 22:41:02 Processing took 216 seconds
```
