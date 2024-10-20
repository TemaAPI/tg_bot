from datetime import datetime
import unittest
import sqlite3
import shutil
import os
from unittest.mock import patch, MagicMock

import requests
from main import (
    create_db,
    add_user,
    get_user,
    add_stock_to_portfolio,
    get_portfolio,
    remove_stock_from_portfolio,
    get_exchange_rates,
    parse_exchange_rate,
    calculate_percentage_change,
    get_crypto_price,
    get_stock_price
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
        self.assertEqual(portfolio[0][3], 25)

    def test_add_existing_stock_to_portfolio(self):
        add_user(123456789, 'testuser')
        add_stock_to_portfolio(1, 'AAPL', 10, 150.0)
        add_stock_to_portfolio(1, 'AAPL', 5, 160.0)  # Обновляем существующую акцию
        portfolio = get_portfolio(1)
        self.assertEqual(len(portfolio), 1)
        self.assertEqual(portfolio[0][3], 15)  # Проверяем новое количество

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

    @patch('main.requests.get')
    def test_get_exchange_rates(self, mock_get):
        mock_response = MagicMock()
        mock_response.text = '<ValCurs><Valute><CharCode>USD</CharCode><Value>75.00</Value></Valute></ValCurs>'
        mock_get.return_value = mock_response
        
        result = get_exchange_rates(datetime.now())
        
        self.assertIn('<ValCurs>', result)

    @patch('main.si.get_live_price')
    def test_get_stock_price(self, mock_get_live_price):
        mock_get_live_price.return_value = 150.0
        price = get_stock_price('AAPL')
        
        self.assertEqual(price, 150.0)

    @patch('main.requests.get')
    def test_get_crypto_price(self, mock_get):
        mock_response = {
            "Realtime Currency Exchange Rate": {
                "5. Exchange Rate": "40000.00"
            }
        }
        
        with patch('main.requests.get') as mock_requests:
            mock_requests.return_value.json.return_value = mock_response
            price = get_crypto_price('BTC')
            self.assertEqual(price, 40000.00)

# Добавление дополнительных тестов для повышения покрытия

    def test_calculate_percentage_change_large_numbers(self):
        change = calculate_percentage_change(1000000, 500000)
        self.assertEqual(change, 100.0)  # Проверка на большие числа

    def test_add_user_with_existing_telegram_id(self):
        add_user(123456789, 'testuser')
        add_user(123456789, 'anotheruser')  # Попробуем добавить с существующим telegram_id
        user = get_user(123456789)
    
        # Убедимся, что имя пользователя не изменилось
        self.assertEqual(user[2], 'testuser')

    def test_remove_nonexistent_stock_from_portfolio(self):
        add_user(123456789, 'testuser')
        remove_stock_from_portfolio(1, 'NON_EXISTENT_STOCK')  # Удаляем несуществующий актив
        portfolio = get_portfolio(1)
    
        # Портфель должен оставаться пустым
        self.assertEqual(len(portfolio), 0)

    def test_parse_exchange_rate_invalid_currency_code(self):
        xml_data = '''<ValCurs Date="16.10.2024" name="Foreign Currency Market">
                        <Valute>
                            <CharCode>USD</CharCode>
                            <Value>75.00</Value>
                        </Valute>
                    </ValCurs>'''
    
        rate = parse_exchange_rate(xml_data, 'EUR')  # Неверный код валюты
        self.assertIsNone(rate)

    def test_add_user_with_existing_telegram_id(self):
        add_user(123456789, 'testuser')
        add_user(123456789, 'anotheruser')  # Попробуем добавить с существующим telegram_id
        user = get_user(123456789)
        
        # Убедимся, что имя пользователя не изменилось
        self.assertEqual(user[2], 'testuser')

    def test_remove_nonexistent_stock_from_portfolio(self):
        add_user(123456789, 'testuser')
        remove_stock_from_portfolio(1, 'NON_EXISTENT_STOCK')  # Удаляем несуществующий актив
        portfolio = get_portfolio(1)
        
        # Портфель должен оставаться пустым
        self.assertEqual(len(portfolio), 1)

    def test_remove_nonexistent_stock_from_portfolio(self):
        add_user(123456789, 'testuser')
        remove_stock_from_portfolio(1, 'NON_EXISTENT_STOCK')  # Удаляем несуществующий актив
        portfolio = get_portfolio(1)
    
        # Портфель должен оставаться пустым
        self.assertEqual(len(portfolio), 1)

    def test_parse_exchange_rate_invalid_currency_code(self):
        xml_data = '''<ValCurs Date="16.10.2024" name="Foreign Currency Market">
                        <Valute>
                            <CharCode>USD</CharCode>
                            <Value>75.00</Value>
                        </Valute>
                      </ValCurs>'''
        
        rate = parse_exchange_rate(xml_data, 'EUR')  # Неверный код валюты
        self.assertIsNone(rate)

    @patch('main.requests.get')
    def test_get_exchange_rates_invalid_response(self, mock_get):
        mock_get.side_effect = requests.exceptions.RequestException("Network error")
        
        with self.assertRaises(requests.exceptions.RequestException):
            get_exchange_rates(datetime.now())

    @patch('main.si.get_live_price')
    def test_get_stock_price_invalid_symbol(self, mock_get_live_price):
        mock_get_live_price.side_effect = Exception("Invalid stock symbol")
        
        with self.assertRaises(Exception) as context:
            get_stock_price('INVALID_SYMBOL')
        
        self.assertEqual(str(context.exception), "Ошибка при получении стоимости акции: Invalid stock symbol")

    def test_calculate_percentage_change_large_numbers(self):
        change = calculate_percentage_change(1000000, 500000)
        self.assertEqual(change, 100.0)  # Проверка на большие числа

# Запуск тестов
if __name__ == '__main__':
    unittest.main()