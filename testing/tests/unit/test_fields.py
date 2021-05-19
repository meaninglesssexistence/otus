# -*- coding: utf-8 -*-

import unittest

from datetime import datetime

from app import api
from tests.cases import cases


class TestCharField(unittest.TestCase):
    @cases(["hoof",
            "horn",
            None])
    def test_ok_field_char(self, args):
        field = api.CharField(nullable=True, required=True)
        self.assertEqual(args, field.clean_data(args))

    @cases([1234,
            b"horn",
            [1, 2, 3]])
    def test_invalid_field_char(self, args):
        field = api.CharField(nullable=False, required=True)
        self.assertRaises(ValueError, field.clean_data, args)


class TestArgumentsField(unittest.TestCase):
    @cases([{},
            None])
    def test_ok_field_arguments(self, args):
        field = api.ArgumentsField(nullable=True, required=True)
        self.assertEqual(args, field.clean_data(args))

    @cases([[],
            "possible args"])
    def test_invalid_field_arguments(self, args):
        field = api.ArgumentsField(nullable=False, required=True)
        self.assertRaises(ValueError, field.clean_data, args)


class TestEmailField(unittest.TestCase):
    @cases(["test@email.com",
            "anothertest@email.org",
            None])
    def test_ok_field_email(self, args):
        field = api.EmailField(nullable=True, required=True)
        self.assertEqual(args, field.clean_data(args))

    @cases(["testemail.com",
            "@",
            "test@"])
    def test_ivalid_field_email(self, args):
        field = api.EmailField(nullable=False, required=True)
        self.assertRaises(ValueError, field.clean_data, args)


class TestPhoneField(unittest.TestCase):
    @cases(["79119009090",
            79118008080])
    def test_ok_field_phone(self, args):
        field = api.PhoneField(nullable=False, required=True)
        self.assertEqual(str(args), field.clean_data(args))

    def test_ok_none_field_phone(self):
        field = api.PhoneField(nullable=True, required=True)
        self.assertIsNone(field.clean_data(None))

    @cases(["7911900909090",
            89118008080,
            "8900"])
    def test_ivalid_field_phone(self, args):
        field = api.PhoneField(nullable=False, required=True)
        self.assertRaises(ValueError, field.clean_data, args)


class TestDateField(unittest.TestCase):
    @cases(["20.09.2009",
            "31.12.1970"])
    def test_ok_field_date(self, args):
        field = api.DateField(nullable=False, required=True)
        self.assertEqual(
            datetime.strptime(args, "%d.%m.%Y"),
            field.clean_data(args))

    def test_ok_none_field_date(self):
        field = api.DateField(nullable=True, required=True)
        self.assertIsNone(field.clean_data(None))

    @cases(["09.2009",
            19112020,
            "31-12-1970"])
    def test_ivalid_field_date(self, args):
        field = api.DateField(nullable=False, required=True)
        self.assertRaises(ValueError, field.clean_data, args)


class TestBirthDayField(unittest.TestCase):
    @cases(["20.09.2009",
            "01.01.2001"])
    def test_ok_field_birthday(self, args):
        field = api.BirthDayField(nullable=False, required=True)
        self.assertEqual(
            datetime.strptime(args, "%d.%m.%Y"),
            field.clean_data(args))

    def test_ok_none_field_birthday(self):
        field = api.BirthDayField(nullable=True, required=True)
        self.assertIsNone(field.clean_data(None))

    @cases(["09.2009",
            "01.01.1950"])
    def test_ivalid_field_birthday(self, args):
        field = api.BirthDayField(nullable=False, required=True)
        self.assertRaises(ValueError, field.clean_data, args)


class TestGenderField(unittest.TestCase):
    @cases([0,
            1,
            2,
            None])
    def test_ok_field_gender(self, args):
        field = api.GenderField(nullable=True, required=True)
        self.assertEqual(args, field.clean_data(args))

    @cases(["0",
            1.1,
            4])
    def test_ivalid_field_gender(self, args):
        field = api.GenderField(nullable=False, required=True)
        self.assertRaises(ValueError, field.clean_data, args)


class TestClientIDsField(unittest.TestCase):
    @cases([[1, 2, 3, 4, 5, 6, 7, 8, 9],
            {1, 2, 3, 4, 5, 6, 7, 8, 9}])
    def test_ok_field_clientids(self, args):
        field = api.ClientIDsField(required=True)
        self.assertSequenceEqual(args, field.clean_data(args))

    @cases([[4, 5.5, 6, 7, 8, 9],
            "5, 6, 7, 8, 9"])
    def test_ivalid_field_clientids(self, args):
        field = api.ClientIDsField(required=True)
        self.assertRaises(ValueError, field.clean_data, args)


if __name__ == "__main__":
    unittest.main()
