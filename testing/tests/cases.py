# -*- coding: utf-8 -*-

from functools import wraps


def cases(cases):
    def decorator(f):
        @wraps(f)
        def wrapper(*args):
            for c in cases:
                new_args = args + (c if isinstance(c, tuple) else (c,))
                try:
                    f(*new_args)
                except Exception as err:
                    msg = f"{err.args[0]}\n\nAbove error caused by this case: {c}"
                    err.args = (msg, *err.args[1:])
                    raise err
        return wrapper
    return decorator
