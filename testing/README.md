# Scoring API Tests

Структура проекта:
```
root/
|
|-- app
|     api.py
|     scoring.py
|     store.py
|
|-- tests
    | cases.py
    |
    |-- integration
    |     test_requests.py
    |     test_store.py
    |
    |-- unit
          test_fields.py
          test_score_request.py
          test_store.py
```

При запуске интеграционных тестов предполагается, что путь до исполняемого
файла `memcached` есть в переменной среды `PATH`.

Запуск тестов производится командой:
```
$ python -m unittest discover -s tests
```
