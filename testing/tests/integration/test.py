# -*- coding: utf-8 -*-

from unittest import TestCase
from unittest.mock import Mock
from unittest import main as run_test
from hashlib import sha512
from datetime import datetime
from app import api
from tests.cases import cases


class TestSuite(TestCase):
    def setUp(self):
        self.context = {}
        self.headers = {}
        self.settings = Mock()

    def get_response(self, request):
        return api.method_handler({"body": request, "headers": self.headers},
                                  self.context,
                                  self.settings)

    def set_valid_auth(self, request):
        if request.get("login") == api.ADMIN_LOGIN:
            msg = datetime.now().strftime("%Y%m%d%H").encode() + api.ADMIN_SALT.encode()
            request["token"] = sha512(msg).hexdigest()
        else:
            msg = request.get("account", "") + request.get("login", "") + api.SALT
            request["token"] = sha512(msg.encode()).hexdigest()

    def test_empty_request(self):
        _, code = self.get_response({})
        self.assertEqual(api.INVALID_REQUEST, code)

    @cases([{"account": "horns&hoofs", "login": "h&f",
             "method": "online_score", "token": "", "arguments": {}},
            {"account": "horns&hoofs", "login": "h&f",
             "method": "online_score", "token": "sdd", "arguments": {}},
            {"account": "horns&hoofs", "login": "admin",
             "method": "online_score", "token": "", "arguments": {}}])
    def test_bad_auth(self, request):
        _, code = self.get_response(request)
        self.assertEqual(api.FORBIDDEN, code)

    @cases([{"account": "horns&hoofs", "login": "h&f", "method": "online_score"},
            {"account": "horns&hoofs", "login": "h&f", "arguments": {}},
            {"account": "horns&hoofs", "method": "online_score", "arguments": {}}])
    def test_invalid_method_request(self, request):
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code)
        self.assertTrue(len(response))

    @cases([{"phone": "89175002040", "email": "stupnikov@otus.ru"},
            {"phone": "79175002040", "birthday": "01.01.2000", "first_name": "s"}])
    def test_invalid_score_request(self, args):
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "online_score", "arguments": args}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, args)
        self.assertTrue(len(response))

    @cases([{"phone": "79175002040", "email": "stupnikov@otus.ru"},
            {"phone": 79175002040, "email": "stupnikov@otus.ru"},
            {"phone": "79175002040", "email": "stupnikov@otus.ru",
             "gender": 1, "birthday": "01.01.2000",
             "first_name": "a", "last_name": "b"}])
    def test_ok_score_request(self, args):
        self.settings.cache_get.return_value = None
        self.settings.cache_set.return_value = None

        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "online_score", "arguments": args}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, args)
        score = response.get("score")
        self.assertTrue(isinstance(score, (int, float)) and score >= 0, args)
        self.assertEqual(sorted(self.context["has"]), sorted(args.keys()))

    @cases([{"phone": "79175002040", "email": "stupnikov@otus.ru"}])
    def test_score_request_caching(self, args):
        self.settings.cache_get.return_value = 43
        self.settings.cache_set.return_value = None

        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "online_score", "arguments": args}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, args)
        score = response.get("score")
        self.assertEqual(score, 43)

    def test_ok_score_admin_request(self):
        args = {"phone": "79175002040", "email": "stupnikov@otus.ru"}
        request = {"account": "horns&hoofs", "login": "admin",
                   "method": "online_score", "arguments": args}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code)
        score = response.get("score")
        self.assertEqual(score, 42)

    @cases([{},
            {"date": "20-07-2017"},
            {"client_ids": [], "date": "1.31.2017"},
            {"client_ids": "", "date": "XXX"}])
    def test_invalid_interests_request(self, args):
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "clients_interests", "arguments": args}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.INVALID_REQUEST, code, args)
        self.assertTrue(len(response))

    @cases([{"client_ids": [1, 2, 3], "date": datetime.today().strftime("%d.%m.%Y")},
            {"client_ids": [1, 2], "date": "19.07.2017"},
            {"client_ids": [0]}])
    def test_ok_interests_request(self, args):
        self.settings.get.return_value = '["test", "object"]'

        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "clients_interests", "arguments": args}
        self.set_valid_auth(request)
        response, code = self.get_response(request)
        self.assertEqual(api.OK, code, args)
        self.assertEqual(len(args["client_ids"]), len(response))
        self.assertTrue(all(v and isinstance(v, list) and all(isinstance(i, str) for i in v) for v in response.values()))
        self.assertEqual(self.context.get("nclients"), len(args["client_ids"]))

if __name__ == "__main__":
    run_test()
