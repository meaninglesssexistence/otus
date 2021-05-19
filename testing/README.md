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
    |     test.py
    |
    |-- unit
          test_fields.py
          test_store.py
```

При запуске интеграционных тестов предполагается, что сервер
`memcached` запущен на том же компьютере и ожидает подключения
на порту "11211". Запуск тестов производится командой:
```
$ python -m unittest discover -s tests
```
