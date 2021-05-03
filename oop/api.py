# -*- coding: utf-8 -*-

import abc
import json
import logging
from hashlib import sha512
from os import EX_SOFTWARE
from typing import NoReturn
from uuid import uuid4
from optparse import OptionParser
from http.server import HTTPServer, BaseHTTPRequestHandler
from re import compile
from datetime import datetime
from dateutil.relativedelta import relativedelta
from scoring import get_score, get_interests


SALT = "Otus"
ADMIN_LOGIN = "admin"
ADMIN_SALT = "42"
OK = 200
BAD_REQUEST = 400
FORBIDDEN = 403
NOT_FOUND = 404
INVALID_REQUEST = 422
INTERNAL_ERROR = 500
ERRORS = {
    BAD_REQUEST: "Bad Request",
    FORBIDDEN: "Forbidden",
    NOT_FOUND: "Not Found",
    INVALID_REQUEST: "Invalid Request",
    INTERNAL_ERROR: "Internal Server Error",
}
UNKNOWN = 0
MALE = 1
FEMALE = 2
GENDERS = {
    UNKNOWN: "unknown",
    MALE: "male",
    FEMALE: "female",
}


class BigBrother(type):
    def __new__(cls, name, bases, dct):
        fields = {}
        for key, value in dct.items():
            if issubclass(type(value), BaseField):
                fields[key] = value
        dct["fields"] = fields
        dct["__init__"] = lambda *args: None
        return super().__new__(cls, name, bases, dct)

    def __call__(self, *args):
        cls = super().__call__(*args)
        args = args[0]
        for key, value in self.fields.items():
            if key in args:
                if value.is_valid(args[key]):
                    setattr(self, key, args[key])
                else:
                    raise TypeError(f"Invalid argument: \"{key}\"")
            else:
                if value.required:
                    raise ValueError(f"Missing argument: \"{key}\"")
                else:
                    setattr(self, key, None)

        if hasattr(self, "is_valid"):
            if not self.is_valid(cls):
                raise ValueError(f"Some arguments missing in {type(self)}")
        return cls


class BaseField(object):
    def __init__(self, required, nullable=False):
        self.required = required
        self.nullable = nullable


class CharField(BaseField):
    def is_valid(self, data):
        if data is None and self.nullable:
            return True
        if isinstance(data, str):
            return True
        return False


class ArgumentsField(BaseField):
    def is_valid(self, data):
        if data is None and self.nullable:
            return True
        if isinstance(data, dict):
            return True
        return False


class EmailField(CharField):
    def is_valid(self, data):
        if data is None and self.nullable:
            return True
        if compile(r"[\w\.]+@[\w\.]+").match(data):
            return True
        return False


class PhoneField(BaseField):
    def is_valid(self, data):
        if data is None and self.nullable:
            return True
        if isinstance(data, (str, int)):
            if len(str(data)) == 11 and str(data).startswith("7"):
                return True
        return False


class DateField(BaseField):
    def is_valid(self, data):
        if data is None and self.nullable:
            return True
        try:
            datetime.strptime(data, "%d.%m.%Y")
            return True
        except (ValueError, TypeError):
            return False


class BirthDayField(BaseField):
    def is_valid(self, data):
        if data is None and self.nullable:
            return True
        try:
            if datetime.strptime(data, "%d.%m.%Y") > datetime.now() - relativedelta(years=70):
                return True
            return False
        except (ValueError, TypeError):
            return False


class GenderField(BaseField):
    def is_valid(self, data):
        if data is None and self.nullable:
            return True
        if isinstance(data, int) and data in (0, 1, 2):
            return True
        return False


class ClientIDsField(BaseField):
    def is_valid(self, data):
        if isinstance(data, (list, tuple, set)):
            if len(data) > 0:
                if all(isinstance(item, int) for item in data):
                    return True
        return False


class ClientsInterestsRequest(object, metaclass=BigBrother):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)


class OnlineScoreRequest(object, metaclass=BigBrother):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def is_valid(self):
        if self.first_name and self.last_name:
            return True
        if self.email and self.phone:
            return True
        if self.birthday and not self.gender is None:
            return True
        return False


class MethodRequest(object, metaclass=BigBrother):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.login == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        msg = datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT
        digest = sha512(msg.encode()).hexdigest()
    else:
        msg = request.account + request.login + SALT
        digest = sha512(msg.encode()).hexdigest()
    if digest == request.token:
        return True
    return False


def method_handler(request, ctx, store):
    try:
        method_request = MethodRequest(request["body"])

        if not check_auth(method_request):
            return "Forbidden", FORBIDDEN

        if method_request.method == "online_score":
            if method_request.is_admin:
                return {"score": 42}, OK

            ctx["has"] = [key for key, val in method_request.arguments.items() if not val is None]

            online_score_request = OnlineScoreRequest(method_request.arguments)
            response = get_score(store,
                                 phone=online_score_request.phone,
                                 email=online_score_request.email,
                                 birthday=online_score_request.birthday,
                                 gender=online_score_request.gender,
                                 first_name=online_score_request.first_name,
                                 last_name=online_score_request.last_name)
            return {"score": response}, OK

        elif method_request.method == "clients_interests":
            clients_interests_request = ClientsInterestsRequest(method_request.arguments)

            ctx["nclients"] = len(clients_interests_request.client_ids)
            interests = {}

            for id in clients_interests_request.client_ids:
                interests[id] = get_interests(store, id)
            return interests, OK
        else:
            return f"Unexpected method: {method_request.method}", BAD_REQUEST
    except Exception as err:
        return f"Invalid requets: {err}", INVALID_REQUEST


class MainHTTPHandler(BaseHTTPRequestHandler):
    router = {
        "method": method_handler
    }
    store = None

    def get_request_id(self, headers):
        return headers.get('HTTP_X_REQUEST_ID', uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            request = json.loads(data_string)
        except:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string, context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path]({"body": request, "headers": self.headers}, context, self.store)
                except Exception as e:
                    logging.exception("Unexpected error: %s" % e)
                    code = INTERNAL_ERROR
            else:
                code = NOT_FOUND

        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if code not in ERRORS:
            r = {"response": response, "code": code}
        else:
            r = {"error": response or ERRORS.get(code, "Unknown Error"), "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r))
        return


if __name__ == "__main__":
    op = OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s', datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
