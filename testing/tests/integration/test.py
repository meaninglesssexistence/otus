# -*- coding: utf-8 -*-

import hashlib
import unittest

from datetime import datetime
from unittest.mock import Mock

from app import api, store


class TestSuite(unittest.TestCase):
    def setUp(self):
        self.context = {}

    def get_response(self, request, store_server):
        return api.method_handler({"body": request, "headers": {}},
                                  self.context, store_server)

    def set_valid_auth(self, request):
        if request.get("login") == api.ADMIN_LOGIN:
            msg = datetime.now().strftime("%Y%m%d%H").encode() + api.ADMIN_SALT.encode()
            request["token"] = hashlib.sha512(msg).hexdigest()
        else:
            msg = request.get("account", "") + request.get("login", "") + api.SALT
            request["token"] = hashlib.sha512(msg.encode()).hexdigest()

    def test_score_request_without_connection(self):
        args = {"phone": "79175002040", "email": "stupnikov@otus.ru",
                "gender": 1, "birthday": "01.01.2000",
                "first_name": "a", "last_name": "b"}
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "online_score", "arguments": args}

        store_server = store.Store(host="not-existed-host")

        self.set_valid_auth(request)
        response, code = self.get_response(request, store_server)
        self.assertEqual(api.OK, code, args)

        self.assertEqual(5.0, response.get("score"))
        self.assertEqual(sorted(self.context["has"]), sorted(args.keys()))

    def test_score_request_with_connection(self):
        args = {"phone": "79175002040", "email": "stupnikov@otus.ru",
                "gender": 1, "birthday": "01.01.2000",
                "first_name": "a", "last_name": "b"}
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "online_score", "arguments": args}

        with store.Store(host="localhost", port=11211) as store_server:
            store_server.client.flush_all()

            self.set_valid_auth(request)
            response, code = self.get_response(request, store_server)
            self.assertEqual(api.OK, code, args)

            self.assertEqual(5.0, response.get("score"))
            self.assertEqual(sorted(self.context["has"]), sorted(args.keys()))

    def test_score_request_caching(self):
        args = {"phone": "79175002040", "email": "stupnikov@otus.ru",
                "gender": 1, "birthday": "01.01.2000",
                "first_name": "a", "last_name": "b"}
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "online_score", "arguments": args}

        with store.Store(host="localhost", port=11211) as store_server:
            store_server.client.flush_all()

            store_server.cache_set("uid:73c1c049b001f8c3aaff38f70bf040ea", 10)

            self.set_valid_auth(request)
            response, code = self.get_response(request, store_server)
            self.assertEqual(api.OK, code, args)

            self.assertEqual(b'10', response.get("score"))
            self.assertEqual(sorted(self.context["has"]), sorted(args.keys()))

    def test_interests_request_without_connection(self):
        args = {"client_ids": [1, 2, 3], "date": "19.07.2017"}
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "clients_interests", "arguments": args}

        store_server = store.Store(host="not-existed-host")

        self.set_valid_auth(request)
        response, code = self.get_response(request, store_server)

        self.assertEqual(api.INVALID_REQUEST, code, args)

    def test_interests_request_with_connection(self):
        args = {"client_ids": [1, 2, 3], "date": "19.07.2017"}
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "clients_interests", "arguments": args}

        with store.Store(host="localhost", port=11211) as store_server:
            store_server.client.flush_all()

            self.set_valid_auth(request)
            response, code = self.get_response(request, store_server)

            self.assertEqual(api.OK, code, args)
            self.assertDictEqual({1: [], 2: [], 3: []}, response)

            store_server.client.set("i:1", '["soccer"]')
            store_server.client.set("i:2", '["box", "fencing"]')

            response, code = self.get_response(request, store_server)

            self.assertEqual(api.OK, code, args)
            self.assertDictEqual({1: ['soccer'], 2: ['box', 'fencing'], 3: []},
                                 response)


if __name__ == "__main__":
    unittest.main()
