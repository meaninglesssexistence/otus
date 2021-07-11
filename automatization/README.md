# OTUServer

## Архитектура
Сервер реализован на основе пула процессов. Используется модуль
`multiprocessing`. За диспетчеризацию подключений отвечает класс
`HttpServer`. За работу с конкретным подключением отвечает класс
`HttpRequest`.

## Использование
```
usage: httpd.py [-h] [-r DOC_ROOT] [-w WORKERS] [-p PORT] [-l {DEBUG,INFO,WARNING,ERROR,CRITICAL}]

Simple HTTP Server.

optional arguments:
  -h, --help            show this help message and exit
  -r DOC_ROOT, --doc-root DOC_ROOT
                        documents root
  -w WORKERS, --workers WORKERS
                        number of workers
  -p PORT, --port PORT  port number
  -l {DEBUG,INFO,WARNING,ERROR,CRITICAL}, --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                        Set the logging level
```

## Результаты тестирования

- Один обработчик
```
$ ./httpd.py -w 1 -l CRITICAL &
$ ab -n 50000 -c 100 -r http://localhost:80/

Concurrency Level:      100
Time taken for tests:   48.599 seconds
Complete requests:      50000
Failed requests:        0
Total transferred:      4700000 bytes
HTML transferred:       0 bytes
Requests per second:    1028.83 [#/sec] (mean)
Time per request:       97.198 [ms] (mean)
Time per request:       0.972 [ms] (mean, across all concurrent requests)
Transfer rate:          94.44 [Kbytes/sec] received

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    0   0.0      0       0
Processing:     1    1   0.1      1       4
Waiting:        1    1   0.1      1       4
Total:          1    1   0.1      1       4

Percentage of the requests served within a certain time (ms)
  50%      1
  66%      1
  75%      1
  80%      1
  90%      1
  95%      1
  98%      1
  99%      1
 100%      4 (longest request)
```

- Пять обработчиков
```
$ ./httpd.py -w 5 -l CRITICAL &
$ ab -n 50000 -c 100 -r http://localhost:80/

Concurrency Level:      100
Time taken for tests:   48.272 seconds
Complete requests:      50000
Failed requests:        0
Total transferred:      4700000 bytes
HTML transferred:       0 bytes
Requests per second:    1035.79 [#/sec] (mean)
Time per request:       96.545 [ms] (mean)
Time per request:       0.965 [ms] (mean, across all concurrent requests)
Transfer rate:          95.08 [Kbytes/sec] received

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    0   0.0      0       0
Processing:     1    1   0.1      1       4
Waiting:        1    1   0.1      1       4
Total:          1    1   0.1      1       4

Percentage of the requests served within a certain time (ms)
  50%      1
  66%      1
  75%      1
  80%      1
  90%      1
  95%      1
  98%      1
  99%      1
 100%      4 (longest request)
```

- Двадцать обработчиков
```
$ ./httpd.py -w 20 -l CRITICAL &
$ ab -n 50000 -c 100 -r http://localhost:80/

Concurrency Level:      100
Time taken for tests:   49.546 seconds
Complete requests:      50000
Failed requests:        0
Total transferred:      4700000 bytes
HTML transferred:       0 bytes
Requests per second:    1009.17 [#/sec] (mean)
Time per request:       99.092 [ms] (mean)
Time per request:       0.991 [ms] (mean, across all concurrent requests)
Transfer rate:          92.64 [Kbytes/sec] received

Connection Times (ms)
              min  mean[+/-sd] median   max
Connect:        0    0   0.0      0       0
Processing:     1    1   0.1      1       4
Waiting:        1    1   0.1      1       4
Total:          1    1   0.1      1       4

Percentage of the requests served within a certain time (ms)
  50%      1
  66%      1
  75%      1
  80%      1
  90%      1
  95%      1
  98%      1
  99%      1
 100%      4 (longest request)
```
