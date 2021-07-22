# -*- coding: utf-8 -*-

import hashlib
import subprocess
import unittest

from datetime import datetime

from app import api, store


class TestSuite(unittest.TestCase):
    MEMC_PORT = 11211

    def setUp(self):
        self.context = {}
        self.memc_proc = subprocess.Popen([
            'memcached', '-p', str(TestSuite.MEMC_PORT)
        ])

    def tearDown(self):
        self.kill_memc()

    def get_response(self, request, memc):
        return api.method_handler(
            {"body": request, "headers": {}},
            self.context, memc
        )

    def set_valid_auth(self, request):
        if request.get("login") == api.ADMIN_LOGIN:
            msg = datetime.now().strftime("%Y%m%d%H").encode() + api.ADMIN_SALT.encode()
            request["token"] = hashlib.sha512(msg).hexdigest()
        else:
            msg = request.get("account", "") + request.get("login", "") + api.SALT
            request["token"] = hashlib.sha512(msg.encode()).hexdigest()

    def kill_memc(self):
        if self.memc_proc.poll() is None:
            self.memc_proc.kill()
            self.memc_proc.wait()

    def test_score_request_without_connection(self):
        """ Проверяем запрос score_request без соединения с сервером.
        """
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
        """ Проверяем запрос score_request с соединением с сервером.
        """
        args = {"phone": "79175002040", "email": "stupnikov@otus.ru",
                "gender": 1, "birthday": "01.01.2000",
                "first_name": "a", "last_name": "b"}
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "online_score", "arguments": args}

        with store.Store(host="localhost", port=TestSuite.MEMC_PORT) as memc:
            memc.client.flush_all()

            self.set_valid_auth(request)
            response, code = self.get_response(request, memc)
            self.assertEqual(api.OK, code, args)

            self.assertEqual(5.0, response.get("score"))
            self.assertEqual(sorted(self.context["has"]), sorted(args.keys()))

    def test_score_request_caching(self):
        """ Проверяем кеширование результатов запроса score_request.
        """

        args = {"phone": "79175002040", "email": "stupnikov@otus.ru",
                "gender": 1, "birthday": "01.01.2000",
                "first_name": "a", "last_name": "b"}
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "online_score", "arguments": args}

        with store.Store(host="localhost", port=TestSuite.MEMC_PORT) as memc:
            memc.client.flush_all()

            memc.cache_set("uid:73c1c049b001f8c3aaff38f70bf040ea", 10)

            self.set_valid_auth(request)
            response, code = self.get_response(request, memc)
            self.assertEqual(api.OK, code, args)

            self.assertEqual(b'10', response.get("score"))
            self.assertEqual(sorted(self.context["has"]), sorted(args.keys()))

    def test_interests_request_without_connection(self):
        """ Проверяем запрос interests_request без соединения с сервером.
        """

        args = {"client_ids": [1, 2, 3], "date": "19.07.2017"}
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "clients_interests", "arguments": args}

        memc = store.Store(host="not-existed-host")

        self.set_valid_auth(request)
        response, code = self.get_response(request, memc)

        self.assertEqual(api.INVALID_REQUEST, code, args)

    def test_interests_request_with_connection(self):
        """ Проверяем запрос interests_request с соединением с сервером.
        """

        args = {"client_ids": [1, 2, 3], "date": "19.07.2017"}
        request = {"account": "horns&hoofs", "login": "h&f",
                   "method": "clients_interests", "arguments": args}

        with store.Store(host="localhost", port=TestSuite.MEMC_PORT) as memc:
            memc.client.flush_all()

            self.set_valid_auth(request)
            response, code = self.get_response(request, memc)

            self.assertEqual(api.OK, code, args)
            self.assertDictEqual({1: [], 2: [], 3: []}, response)

            memc.client.set("i:1", '["soccer"]')
            memc.client.set("i:2", '["box", "fencing"]')

            response, code = self.get_response(request, memc)

            self.assertEqual(api.OK, code, args)
            self.assertDictEqual({1: ['soccer'], 2: ['box', 'fencing'], 3: []},
                                 response)


if __name__ == "__main__":
    unittest.main()
