# -*- coding: utf-8 -*-

import unittest

from app import api
from tests.cases import cases


class TestScoreRequestValidation(unittest.TestCase):
    @cases([{"phone": "79175002040", "email": "stupnikov@otus.ru",
             "gender": 1, "birthday": "01.01.2000",
             "first_name": "a", "last_name": "b"},
            {"phone": "79175002040", "email": "stupnikov@otus.ru"},
            {"gender": 1, "birthday": "01.01.2000"},
            {"first_name": "a", "last_name": "b"}])
    def test_ok_arguments_combination(self, args):
        request = api.OnlineScoreRequest(args)
        self.assertTrue(request)

    @cases([{},
            {"email": "stupnikov@otus.ru"},
            {"gender": 1, "last_name": "b"},
            {"first_name": "a", "birthday": "01.01.2000"}])
    def test_ivalid_arguments_combination(self, args):
        self.assertRaises(ValueError, api.OnlineScoreRequest, args)

if __name__ == "__main__":
    unittest.main()
