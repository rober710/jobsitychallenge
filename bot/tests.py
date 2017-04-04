# encoding: utf-8

"""Casos de prueba para las llamadas a las APIs de Yahoo! del Bot."""

import unittest

from unittest import TestCase

from .server import Bot


class BotRequestTest(TestCase):

    def setUp(self):
        self.bot = Bot(use_rabbitmq=False)

    def test_stocks_api_existing_company(self):
        response = self.bot.query_stock('AAPL')
        print('Stocks API AAPL: ' + repr(response))
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.get('error', None))
        self.assertFalse(response.get('error'))
        self.assertIsInstance(response.get('message', None), str)
        self.assertIsInstance(response.get('price', None), float)
        self.assertIsInstance(response.get('name', None), str)

    def test_stocks_api_nonexising_company(self):
        response = self.bot.query_stock('sfsklgg')
        print('Stocks API sfsklgg: ' + repr(response))
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.get('error', None))
        self.assertTrue(response.get('error'))
        self.assertIsInstance(response.get('message', None), str)

    def test_range_api_existing_company(self):
        response = self.bot.query_day_range('AAPL')
        print('Range API AAPL: ' + repr(response))
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.get('error', None))
        self.assertFalse(response.get('error'))
        self.assertIsInstance(response.get('results', None), (list, tuple))
        self.assertTrue(len(response.get('results')) > 0)

        obj = response.get('results')[0]
        self.assertIsInstance(obj, dict)
        self.assertIsInstance(obj.get('companyCode', None), str)
        self.assertIsInstance(obj.get('message', None), str)
        self.assertIsInstance(obj.get('name', None), str)
        self.assertIsInstance(obj.get('daysLow', None), float)
        self.assertIsInstance(obj.get('daysHigh', None), float)
        self.assertFalse(obj.get('error', True))

    def test_range_api_incomplete_info(self):
        """
        Prueba la llamada al API Range usando una compañía que devuelve datos incompletos.
        """
        response = self.bot.query_day_range('APPL')
        print('Range API APPL: ' + repr(response))
        self.assertIsNotNone(response)
        self.assertIsNotNone(response.get('error', None))
        self.assertFalse(response.get('error'))
        self.assertIsInstance(response.get('results', None), (list, tuple))
        self.assertTrue(len(response.get('results')) == 1)

        obj = response.get('results')[0]
        self.assertIsInstance(obj, dict)
        self.assertIsInstance(obj.get('message', None), str)
        self.assertTrue(obj.get('error', False))

    def test_range_api_multiple_companies(self):
        response = self.bot.query_day_range(['AAPL', 'APPL', 'sldfmslf'])
        print('Range API [AAPL, APPL, sldfmslf]: ' + repr(response))

        self.assertIsNotNone(response)
        self.assertIsNotNone(response.get('error', None))
        self.assertFalse(response.get('error'))
        self.assertIsInstance(response.get('results', None), (list, tuple))
        self.assertTrue(len(response.get('results')) == 3)

        obj = response.get('results')[0]
        self.assertIsInstance(obj, dict)
        self.assertIsInstance(obj.get('companyCode', None), str)
        self.assertIsInstance(obj.get('message', None), str)
        self.assertIsInstance(obj.get('name', None), str)
        self.assertIsInstance(obj.get('daysLow', None), float)
        self.assertIsInstance(obj.get('daysHigh', None), float)
        self.assertFalse(obj.get('error', True))

        obj = response.get('results')[1]
        self.assertIsInstance(obj, dict)
        self.assertIsInstance(obj.get('message', None), str)
        self.assertTrue(obj.get('error', False))

        obj = response.get('results')[2]
        self.assertIsInstance(obj, dict)
        self.assertIsInstance(obj.get('message', None), str)
        self.assertTrue(obj.get('error', False))

    def test_range_api_invalid(self):
        """Prueba el método del API Range cuando no se envían datos válidos."""
        response = self.bot.query_day_range([])
        print('Range API []: ' + repr(response))

        self.assertIsNotNone(response)
        self.assertIsNotNone(response.get('error', None))
        self.assertTrue(response.get('error', False))
        self.assertIsInstance(response.get('message', None), str)
        self.assertEqual(response.get('code', None), 'BOT01')


if __name__ == '__main__':
    unittest.main()