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

Запуск тестов производится командой:
```
$ python -m unittest discover -s tests
```
