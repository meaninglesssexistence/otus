# -*- coding: utf-8 -*-

from unittest import TestCase
from unittest import main as run_tests
from app import api
from tests.cases import cases


class TestSuite(TestCase):
    @cases(["hoof",
            "horn",
            None])
    def test_ok_field_char(self, args):
        field = api.CharField(nullable=True, required=True)
        self.assertTrue(field.is_valid(args))

    @cases([1234,
            b"horn",
            [1, 2, 3]])
    def test_invalid_field_char(self, args):
        field = api.CharField(nullable=False, required=True)
        self.assertFalse(field.is_valid(args))

    @cases([{},
            None])
    def test_ok_field_arguments(self, args):
        field = api.ArgumentsField(nullable=True, required=True)
        self.assertTrue(field.is_valid(args))

    @cases([[],
            "possible args"])
    def test_invalid_field_arguments(self, args):
        field = api.ArgumentsField(nullable=False, required=True)
        self.assertFalse(field.is_valid(args))

    @cases(["test@email.com",
            "anothertest@email.org",
            None])
    def test_ok_field_email(self, args):
        field = api.EmailField(nullable=True, required=True)
        self.assertTrue(field.is_valid(args))

    @cases(["testemail.com",
            "@",
            "test@"])
    def test_ivalid_field_email(self, args):
        field = api.EmailField(nullable=False, required=True)
        self.assertFalse(field.is_valid(args))

    @cases(["79119009090",
            79118008080,
            None])
    def test_ok_field_phone(self, args):
        field = api.PhoneField(nullable=True, required=True)
        self.assertTrue(field.is_valid(args))

    @cases(["7911900909090",
            89118008080,
            "8900"])
    def test_ivalid_field_phone(self, args):
        field = api.PhoneField(nullable=False, required=True)
        self.assertFalse(field.is_valid(args))

    @cases(["20.09.2009",
            "31.12.1970",
            None])
    def test_ok_field_date(self, args):
        field = api.DateField(nullable=True, required=True)
        self.assertTrue(field.is_valid(args))

    @cases(["09.2009",
            19112020,
            "31-12-1970"])
    def test_ivalid_field_date(self, args):
        field = api.DateField(nullable=False, required=True)
        self.assertFalse(field.is_valid(args))

    @cases(["20.09.2009",
            "01.01.2001",
            None])
    def test_ok_field_birthday(self, args):
        field = api.BirthDayField(nullable=True, required=True)
        self.assertTrue(field.is_valid(args))

    @cases(["09.2009",
            "01.01.1950"])
    def test_ivalid_field_birthday(self, args):
        field = api.BirthDayField(nullable=False, required=True)
        self.assertFalse(field.is_valid(args))

    @cases([0,
            1,
            2,
            None])
    def test_ok_field_gender(self, args):
        field = api.GenderField(nullable=True, required=True)
        self.assertTrue(field.is_valid(args))

    @cases(["0",
            1.1,
            4])
    def test_ivalid_field_gender(self, args):
        field = api.GenderField(nullable=False, required=True)
        self.assertFalse(field.is_valid(args))

    @cases([[1, 2, 3, 4, 5, 6, 7, 8, 9],
            {1, 2, 3, 4, 5, 6, 7, 8, 9}])
    def test_ok_field_clientids(self, args):
        field = api.ClientIDsField(required=True)
        self.assertTrue(field.is_valid(args))

    @cases([[4, 5.5, 6, 7, 8, 9],
            "5, 6, 7, 8, 9"])
    def test_ivalid_field_clientids(self, args):
        field = api.ClientIDsField(required=True)
        self.assertFalse(field.is_valid(args))

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
    run_tests()
