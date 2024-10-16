import os
import shutil
import unittest
import sqlite3
from main import (
    create_db,
    add_user,
    get_user,
    add_stock_to_portfolio,
    get_portfolio,
    remove_stock_from_portfolio,
    parse_exchange_rate,
    calculate_percentage_change,
)

DATABASE_NAME = os.path.join('app_data', 'finance_bot.db')
TEST_DATABASE_NAME = os.path.join('app_data', 'test_finance_bot.db')

class TestFinanceBot(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Создаем основную базу данных и копируем её для тестов
        create_db()
        shutil.copy(DATABASE_NAME, TEST_DATABASE_NAME)

    @classmethod
    def tearDownClass(cls):
        # Удаляем тестовую базу данных после всех тестов
        if os.path.exists(TEST_DATABASE_NAME):
            os.remove(TEST_DATABASE_NAME)

    def setUp(self):
        # В каждом тесте используем копию базы данных
        self.connection = sqlite3.connect(TEST_DATABASE_NAME)
        self.cursor = self.connection.cursor()

    def tearDown(self):
        # Закрываем соединение после каждого теста
        self.connection.close()

    def test_add_user(self):
        add_user(123456789, 'testuser')
        user = get_user(123456789)
        self.assertIsNotNone(user)
        self.assertEqual(user[2], 'testuser')

    def test_get_user_not_found(self):
        user = get_user(999999999)
        self.assertIsNone(user)

    def test_add_stock_to_portfolio(self):
        add_user(123456789, 'testuser')
        add_stock_to_portfolio(1, 'AAPL', 10, 150.0)
        portfolio = get_portfolio(1)
        self.assertEqual(len(portfolio), 1)
        self.assertEqual(portfolio[0][2], 'AAPL')
        self.assertEqual(portfolio[0][3], 10)

    def test_remove_stock_from_portfolio(self):
        add_user(123456789, 'testuser')
        add_stock_to_portfolio(1, 'AAPL', 10, 150.0)
        remove_stock_from_portfolio(1, 'AAPL')
        portfolio = get_portfolio(1)
        self.assertEqual(len(portfolio), 0)

    def test_calculate_percentage_change(self):
        change = calculate_percentage_change(200, 100)
        self.assertEqual(change, 100.0)

    def test_calculate_percentage_change_zero_division(self):
        change = calculate_percentage_change(100, 0)
        self.assertIsNone(change)

    def test_parse_exchange_rate(self):
        xml_data = '''<ValCurs Date="16.10.2024" name="Foreign Currency Market">
                        <Valute>
                            <CharCode>USD</CharCode>
                            <Value>75.00</Value>
                        </Valute>
                      </ValCurs>'''
        rate = parse_exchange_rate(xml_data, 'USD')
        self.assertEqual(rate, 75.00)

# Запуск тестов
if __name__ == '__main__':
    unittest.main()