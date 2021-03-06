# -*- coding: utf-8 -*-

import hashlib
import json
import logging
import optparse
import re
import uuid
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime
from dateutil.relativedelta import relativedelta
import scoring


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
        return super().__new__(cls, name, bases, dct)


class BaseRequest:
    def __init__(self, args):
        self.error_list = None
        self.cleaned_data = {}
        for field_name, field_value in args.items():
            setattr(self, field_name, field_value)

    def is_valid(self):
        if self.error_list is not None:
            return False

        for key, value in self.__class__.fields.items():
            if key in self.__dict__:
                try:
                    self.cleaned_data[key] = value.clean(self.__dict__[key])
                except Exception as err:
                    self._append_error(f"Invalid '{key}' value: {err}")
            else:
                if value.required:
                    self._append_error(f"Missing argument: '{key}'")
                else:
                    self.cleaned_data[key] = None

        return not self.error_list

    def _append_error(self, err):
        if not self.error_list:
            self.error_list = []
        self.error_list.append(err)

    @property
    def errors(self):
        if self.error_list is None:
            self.is_valid()
        return self.error_list if self.error_list else []


class BaseField(object):
    def __init__(self, required, nullable=False):
        self.required = required
        self.nullable = nullable

    def clean(self, data):
        if data is None and not self.nullable:
            raise ValueError("Value cannot be None")
        return data


class CharField(BaseField):
    def clean(self, data):
        super().clean(data)
        if data and not isinstance(data, str):
            raise ValueError("Value type should be str")
        return data


class ArgumentsField(BaseField):
    def clean(self, data):
        super().clean(data)
        if data is not None and not isinstance(data, dict):
            raise ValueError("Value type should be dict")
        return data


class EmailField(CharField):
    def clean(self, data):
        super().clean(data)
        if data and not re.compile(r"[\w\.]+@[\w\.]+").match(data):
            raise ValueError("Email has invalid format")
        return data


class PhoneField(BaseField):
    def clean(self, data):
        super().clean(data)
        if not data:
            return
        if not isinstance(data, (str, int)):
            raise ValueError("Phone number should be int")
        if len(str(data)) != 11:
            raise ValueError("Phone number should has 11 digits")
        if not str(data).startswith("7"):
            raise ValueError("Phone number should start from 7")
        return str(data)


class DateField(BaseField):
    def clean(self, data):
        super().clean(data)
        if not data:
            return
        try:
            return datetime.strptime(data, "%d.%m.%Y")
        except (ValueError, TypeError):
            raise ValueError("Invalid date format")


class BirthDayField(DateField):
    def clean(self, data):
        date = super().clean(data)
        if not data:
            return

        if date < datetime.now() - relativedelta(years=70):
            raise ValueError("Age should be less then 70 years")
        return date

class GenderField(BaseField):
    def clean(self, data):
        super().clean(data)
        if data and not isinstance(data, int):
            raise ValueError("Gender should be integer")
        if data and data not in (0, 1, 2):
            raise ValueError("Gender should be number in (0, 1, 2)")
        return data


class ClientIDsField(BaseField):
    def clean(self, data):
        if not isinstance(data, (list, tuple, set)):
            raise ValueError("Client IDs should be list, tuple or set")
        if not data:
            raise ValueError(f"Client IDs cannot be empty")
        if any(not isinstance(item, int) for item in data):
            raise ValueError(f"Each client ID should be integer")
        return data


class ClientsInterestsRequest(BaseRequest, metaclass=BigBrother):
    client_ids = ClientIDsField(required=True)
    date = DateField(required=False, nullable=True)


class OnlineScoreRequest(BaseRequest, metaclass=BigBrother):
    first_name = CharField(required=False, nullable=True)
    last_name = CharField(required=False, nullable=True)
    email = EmailField(required=False, nullable=True)
    phone = PhoneField(required=False, nullable=True)
    birthday = BirthDayField(required=False, nullable=True)
    gender = GenderField(required=False, nullable=True)

    def is_valid(self):
        if not super().is_valid():
            return False
        if self.cleaned_data['first_name'] and self.cleaned_data['last_name']:
            return True
        if self.cleaned_data['email'] and self.cleaned_data['phone']:
            return True
        if self.cleaned_data['birthday'] and self.cleaned_data['gender'] is not None:
            return True
        self.error_list.append(f"Missed required pair of arguments")
        return False


class MethodRequest(BaseRequest, metaclass=BigBrother):
    account = CharField(required=False, nullable=True)
    login = CharField(required=True, nullable=True)
    token = CharField(required=True, nullable=True)
    arguments = ArgumentsField(required=True, nullable=True)
    method = CharField(required=True, nullable=False)

    @property
    def is_admin(self):
        return self.cleaned_data['login'] == ADMIN_LOGIN


def check_auth(request):
    if request.is_admin:
        msg = datetime.now().strftime("%Y%m%d%H") + ADMIN_SALT
        digest = hashlib.sha512(msg.encode()).hexdigest()
    else:
        msg = request.account + request.login + SALT
        digest = hashlib.sha512(msg.encode()).hexdigest()
    if digest == request.token:
        return True
    return False


def online_score_handler(method_request, ctx, store):
    if method_request.is_admin:
        return {"score": 42}, OK

    arguments = method_request.cleaned_data['arguments']
    ctx["has"] = [
        key for key, val in arguments.items() if val is not None
    ]

    request = OnlineScoreRequest(arguments)
    if not request.is_valid():
        return f"Invalid requets: {request.errors}", INVALID_REQUEST

    response = scoring.get_score(store,
                                 phone=request.cleaned_data['phone'],
                                 email=request.cleaned_data['email'],
                                 birthday=request.cleaned_data['birthday'],
                                 gender=request.cleaned_data['gender'],
                                 first_name=request.cleaned_data['first_name'],
                                 last_name=request.cleaned_data['last_name'])
    return {"score": response}, OK


def clients_interests_handler(method_request, ctx, store):
    request = ClientsInterestsRequest(method_request.cleaned_data['arguments'])
    if not request.is_valid():
        return f"Invalid requets: {request.errors}", INVALID_REQUEST

    client_ids = request.cleaned_data['client_ids']
    ctx["nclients"] = len(client_ids)
    interests = {}

    for id in client_ids:
        interests[id] = scoring.get_interests(store, id)
    return interests, OK


def method_handler(request, ctx, store):
    try:
        method_request = MethodRequest(request["body"])
        if not method_request.is_valid():
            return f"Invalid requets: {method_request.errors}", INVALID_REQUEST

        if not check_auth(method_request):
            return "Forbidden", FORBIDDEN

        if method_request.method == "online_score":
            return online_score_handler(method_request, ctx, store)
        elif method_request.method == "clients_interests":
            return clients_interests_handler(method_request, ctx, store)
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
        return headers.get('HTTP_X_REQUEST_ID', uuid.uuid4().hex)

    def do_POST(self):
        response, code = {}, OK
        context = {"request_id": self.get_request_id(self.headers)}
        request = None
        try:
            data_string = self.rfile.read(int(self.headers['Content-Length']))
            request = json.loads(data_string)
        except Exception:
            code = BAD_REQUEST

        if request:
            path = self.path.strip("/")
            logging.info("%s: %s %s" % (self.path, data_string,
                                        context["request_id"]))
            if path in self.router:
                try:
                    response, code = self.router[path](
                        {"body": request, "headers": self.headers},
                        context, self.store)
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
            r = {"error": response or ERRORS.get(code, "Unknown Error"),
                 "code": code}
        context.update(r)
        logging.info(context)
        self.wfile.write(json.dumps(r))
        return


if __name__ == "__main__":
    op = optparse.OptionParser()
    op.add_option("-p", "--port", action="store", type=int, default=8080)
    op.add_option("-l", "--log", action="store", default=None)
    (opts, args) = op.parse_args()
    logging.basicConfig(filename=opts.log, level=logging.INFO,
                        format='[%(asctime)s] %(levelname).1s %(message)s',
                        datefmt='%Y.%m.%d %H:%M:%S')
    server = HTTPServer(("localhost", opts.port), MainHTTPHandler)
    logging.info("Starting server at %s" % opts.port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
