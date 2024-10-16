import os
import sqlite3
import requests
from dotenv import load_dotenv
from yahoo_fin import stock_info as si
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.utils import executor
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

load_dotenv()

API_TOKEN = os.getenv('API_TOKEN')
ALPHA_VANTAGE_API_KEY = os.getenv('ALPHA_VANTAGE_API_KEY')

# Создание объектов бота и диспетчера
bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

DATABASE_NAME = os.path.join('app_data', 'finance_bot.db')

# Функция для создания базы данных и таблиц
def create_db():
    
    if not os.path.exists('app_data'):
        os.makedirs('app_data')

    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    # Создание таблицы пользователей
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE,
        username TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Создание таблицы портфеля
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        stock_symbol TEXT,
        quantity INTEGER,
        purchase_price REAL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    )
    ''')

    connection.commit()
    connection.close()

# Функции для работы с базой данных
def add_user(telegram_id, username):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()
    
    cursor.execute('''
    INSERT OR IGNORE INTO users (telegram_id, username) VALUES (?, ?)
    ''', (telegram_id, username))
    
    connection.commit()
    connection.close()

def get_user(telegram_id):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()
    
    cursor.execute('''
    SELECT * FROM users WHERE telegram_id = ?
    ''', (telegram_id,))
    
    user = cursor.fetchone()
    
    connection.close()
    
    return user

def add_stock_to_portfolio(user_id, stock_symbol, quantity, purchase_price):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()

    # Проверяем, существует ли уже актив с таким символом в портфеле
    cursor.execute('''
    SELECT quantity, purchase_price FROM portfolio WHERE user_id = ? AND stock_symbol = ?
    ''', (user_id, stock_symbol))
    
    existing_stock = cursor.fetchone()

    if existing_stock:
        existing_quantity, existing_price = existing_stock
        
        # Обновляем количество и пересчитываем среднюю цену покупки
        new_quantity = existing_quantity + quantity
        
        # Рассчитываем новую среднюю цену покупки с округлением до двух знаков после запятой
        total_cost = (existing_price * existing_quantity) + (purchase_price * quantity)
        new_average_price = round(total_cost / new_quantity, 2)
        
        cursor.execute('''
        UPDATE portfolio SET quantity = ?, purchase_price = ? WHERE user_id = ? AND stock_symbol = ?
        ''', (new_quantity, new_average_price, user_id, stock_symbol))
        
    else:
        # Если актив не существует, добавляем его в портфель
        cursor.execute('''
        INSERT INTO portfolio (user_id, stock_symbol, quantity, purchase_price) VALUES (?, ?, ?, ?)
        ''', (user_id, stock_symbol, quantity, purchase_price))

    connection.commit()
    connection.close()

def get_portfolio(user_id):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()
    
    cursor.execute('''
    SELECT * FROM portfolio WHERE user_id = ?
    ''', (user_id,))
    
    portfolio = cursor.fetchall()
    
    connection.close()
    
    return portfolio

def remove_stock_from_portfolio(user_id, stock_symbol):
    connection = sqlite3.connect(DATABASE_NAME)
    cursor = connection.cursor()
    
    cursor.execute('''
    DELETE FROM portfolio WHERE user_id = ? AND stock_symbol = ?
    ''', (user_id, stock_symbol))
    
    connection.commit()
    connection.close()

# Интеграция с Банком России для получения курса валют
def get_exchange_rates(date):
   url = f'http://www.cbr.ru/scripts/XML_daily.asp?date_req={date.strftime("%d/%m/%Y")}'
   response = requests.get(url)
   response.raise_for_status()  # Raise an error for bad responses
   return response.text

def parse_exchange_rate(xml_data, currency_code):
   root = ET.fromstring(xml_data)
   currency_value = root.find(f'.//Valute[CharCode="{currency_code}"]/Value')
   
   if currency_value is not None:
       return float(currency_value.text.replace(',', '.'))
   else:
       return None

def calculate_percentage_change(current_value, previous_value):
   if previous_value == 0:
       return None  # Avoid division by zero
   return ((current_value - previous_value) / previous_value) * 100

# Получение стоимости криптовалюты из Alpha Vantage
def get_crypto_price(symbol):
   url = f'https://www.alphavantage.co/query?function=CURRENCY_EXCHANGE_RATE&from_currency={symbol}&to_currency=USD&apikey={ALPHA_VANTAGE_API_KEY}'
   response = requests.get(url)
   data = response.json()

   if "Realtime Currency Exchange Rate" in data:
       price_info = data["Realtime Currency Exchange Rate"]
       current_price = float(price_info["5. Exchange Rate"])
       return current_price
   else:
       return None

# Получение стоимости акций из Yahoo Finance с использованием yahoo_fin
def get_stock_price(symbol):
   try:
       current_price = si.get_live_price(symbol)  # Используем метод из библиотеки yahoo_fin.
       return current_price
   except Exception as e:
       raise Exception(f"Ошибка при получении стоимости акции: {str(e)}")

# Создаем базу данных при запуске бота
create_db()

@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
   telegram_id = message.from_user.id
   user = get_user(telegram_id)

   if user:
       await message.reply(f"Здравствуйте, {message.from_user.full_name}! Я ваш личный финансовый ассистент.", reply_markup=main_menu())
   else:
       await message.reply(f"Здравствуйте, {message.from_user.full_name}! Я ваш личный финансовый ассистент. Пожалуйста, зарегистрируйтесь.", reply_markup=registration_menu())

def main_menu():
   markup = ReplyKeyboardMarkup(resize_keyboard=True)
   button1 = KeyboardButton("Мой портфель")
   button2 = KeyboardButton("Курс валют")
   button3 = KeyboardButton("Криптовалюта")  # Новая кнопка для криптовалюты
   button4 = KeyboardButton("Биржа")  # Новая кнопка для акций
   
   markup.add(button1).add(button2).add(button3).add(button4)
   
   return markup

def registration_menu():
   markup = ReplyKeyboardMarkup(resize_keyboard=True)
   button_register = KeyboardButton("Регистрация")
   
   markup.add(button_register)
   
   return markup

@dp.message_handler(lambda message: message.text == "Регистрация")
async def register_user(message: types.Message):
   telegram_id = message.from_user.id
   username = message.from_user.username
   
   # Добавляем пользователя в базу данных
   add_user(telegram_id, username)

   await message.reply(f"Вы успешно зарегистрированы! Теперь вы можете использовать кнопки для управления своим портфелем.", reply_markup=main_menu())

@dp.message_handler(lambda message: message.text == "Мой портфель")
async def portfolio_menu(message: types.Message):
   await message.reply("Выберите действие:", reply_markup=portfolio_options())

def portfolio_options():
   markup = ReplyKeyboardMarkup(resize_keyboard=True)
   
   button1 = KeyboardButton("Мои активы")
   button2 = KeyboardButton("Добавить актив")
   button3 = KeyboardButton("Удалить актив")
   button_back_main_menu = KeyboardButton("Назад в главное меню")
   
   markup.add(button1).add(button2).add(button3).add(button_back_main_menu)
   
   return markup

@dp.message_handler(lambda message: message.text == "Курс валют")
async def exchange_rate_prompt(message: types.Message):
   await message.reply("Введите код валюты (например, USD):", reply_markup=currency_back_button())
   
   # Устанавливаем состояние для ввода кода валюты
   await dp.current_state(user=message.from_user.id).set_state("waiting_for_currency_code")

@dp.message_handler(state="waiting_for_currency_code", content_types=types.ContentTypes.TEXT)
async def process_currency_code(message: types.Message, state: FSMContext):
   currency_code = message.text.strip().upper()  # Приводим код к верхнему регистру
   
   today = datetime.now()
   yesterday_date=today - timedelta(days=1)

   try:
       today_rates_xml=get_exchange_rates(today) 
       yesterday_rates_xml=get_exchange_rates(yesterday_date) 

       current_rate=parse_exchange_rate(today_rates_xml,currency_code) 
       previous_rate=parse_exchange_rate(yesterday_rates_xml,currency_code) 

       if current_rate is not None and previous_rate is not None:
           percentage_change=calculate_percentage_change(current_rate ,previous_rate) 

           await message.reply(
               f"Текущий курс {currency_code}: {current_rate:.2f} руб.\n"
               f"Курс {currency_code} вчера: {previous_rate:.2f} руб.\n"
               f"Изменение курса по сравнению с вчерашним днем: {percentage_change:.2f}%"
           )
       else:
           await message.reply(f"Не удалось получить курс для валюты: {currency_code}")
       
       # Сбрасываем состояние после получения курса.
       await state.finish()

   except Exception as e:
       await message.reply(f"Произошла ошибка при получении курса валют: {str(e)}")

@dp.message_handler(lambda message: message.text == "Криптовалюта")
async def crypto_prompt(message: types.Message):
  await message.reply("Введите код криптовалюты (например BTC):", reply_markup=currency_back_button())
  
  # Устанавливаем состояние для ввода кода криптовалюты.
  await dp.current_state(user=message.from_user.id).set_state("waiting_for_crypto_code")

@dp.message_handler(state="waiting_for_crypto_code", content_types=types.ContentTypes.TEXT)
async def process_crypto_code(message: types.Message,state:FSMContext):
  crypto_code=message.text.strip().upper() 

  try:
      current_price=get_crypto_price(crypto_code) 

      if current_price is not None:
          yesterday_date=datetime.now()-timedelta(days=1) 
          previous_day_price=get_crypto_price(crypto_code) 

          if previous_day_price is not None:
              percentage_change=(current_price-previous_day_price)/previous_day_price*100 

              await message.reply(
                  f"Текущая стоимость {crypto_code}: {current_price:.2f} USD\n"
                  f"Стоимость {crypto_code} вчера: {previous_day_price:.2f} USD\n"
                  f"Изменение стоимости по сравнению с вчерашним днем: {percentage_change:.2f}%"
              )
          else:
              await message.reply(f"Не удалось получить стоимость для криптовалюты за вчерашний день.")
      else:
          await message.reply(f"Не удалось получить стоимость для криптовалюты: {crypto_code}")

      # Сбрасываем состояние после получения стоимости.
      await state.finish()

  except Exception as e:
      await message.reply(f"Произошла ошибка при получении стоимости криптовалюты: {str(e)}")

@dp.message_handler(lambda message: message.text == "Биржа")
async def stock_prompt(message: types.Message):
  await message.reply("Введите символ акции (например AAPL):", reply_markup=currency_back_button())
  
  # Устанавливаем состояние для ввода символа акции.
  await dp.current_state(user=message.from_user.id).set_state("waiting_for_stock_symbol")

@dp.message_handler(state="waiting_for_stock_symbol", content_types=types.ContentTypes.TEXT)
async def process_stock_symbol(message: types.Message,state:FSMContext):
  stock_symbol=message.text.strip().upper() 

  try:
      current_stock_price=get_stock_price(stock_symbol) 

      if current_stock_price is not None:
          yesterday_date=datetime.now()-timedelta(days=1) 
          previous_stock_price=get_stock_price(stock_symbol) 

          if previous_stock_price is not None:
              percentage_change=(current_stock_price-previous_stock_price)/previous_stock_price*100 

              await message.reply(
                  f"Текущая стоимость акции {stock_symbol}: {current_stock_price:.2f} USD\n"
                  f"Стоимость акции {stock_symbol} вчера: {previous_stock_price:.2f} USD\n"
                  f"Изменение стоимости по сравнению с вчерашним днем: {percentage_change:.2f}%"
              )
          else:
              await message.reply(f"Не удалось получить стоимость акции за вчерашний день.")
      else:
          await message.reply(f"Не удалось получить стоимость акции: {stock_symbol}")

      # Сбрасываем состояние после получения стоимости.
      await state.finish()

  except Exception as e:
      await message.reply(f"Произошла ошибка при получении стоимости акции: {str(e)}")

@dp.message_handler(lambda message: message.text == "Мои активы")
async def show_portfolio(message: types.Message):
  telegram_id=message.from_user.id 
  user=get_user(telegram_id)

  if user:
      user_id=user[0] 
      portfolio_items=get_portfolio(user_id)

      if portfolio_items:
          response="Ваши активы:\n"
          for item in portfolio_items:
              response+=f"Акция: {item[2]}, Количество: {item[3]}, Цена покупки: {item[4]}\n"
          await message.reply(response)
      else:
          await message.reply("Ваш портфель пуст.")

@dp.message_handler(lambda message: message.text == "Добавить актив")
async def add_stock_prompt(message: types.Message):
  await message.reply("Укажите название актива:", reply_markup=back_button())
  
  # Устанавливаем состояние для добавления актива.
  await dp.current_state(user=message.from_user.id).set_state("waiting_for_stock_name")

@dp.message_handler(state="waiting_for_stock_name", content_types=types.ContentTypes.TEXT)
async def process_stock_name(message: types.Message,state:FSMContext):
  stock_name=message.text.strip() 
  
  # Сохраняем название актива в состоянии.
  await state.update_data(stock_name=stock_name)

  await message.reply("Укажите количество:")
  
  # Переходим к следующему состоянию.
  await dp.current_state(user=message.from_user.id).set_state("waiting_for_quantity")

@dp.message_handler(state="waiting_for_quantity", content_types=types.ContentTypes.TEXT)
async def process_quantity(message: types.Message,state:FSMContext):
  quantity_text=message.text.strip()

  if not quantity_text.isdigit():
      await message.reply("Пожалуйста введите корректное количество.")
      return

  quantity=int(quantity_text)

  # Сохраняем количество в состоянии.
  await state.update_data(quantity=quantity)

  await message.reply("Укажите цену за 1 единицу актива:")
  
  # Переходим к следующему состоянию.
  await dp.current_state(user=message.from_user.id).set_state("waiting_for_price")

@dp.message_handler(state="waiting_for_price", content_types=types.ContentTypes.TEXT)
async def process_price(message: types.Message,state:FSMContext):
  price_text=message.text.strip()

  try:
      price_per_unit=float(price_text) 
      
      # Получаем данные из состояния.
      data=await state.get_data() 
      stock_name=data.get('stock_name')
      quantity=data.get('quantity')

      total_price=price_per_unit*quantity 

      telegram_id=message.from_user.id 
      user=get_user(telegram_id)

      if user:
          user_id=user[0] 
          add_stock_to_portfolio(user_id ,stock_name ,quantity ,total_price) 
          await message.reply(f"Акция {stock_name} добавлена в ваш портфель. Общая стоимость:{total_price:.2f}.")
      
      # Сбрасываем состояние после добавления актива.
      await state.finish()

  except ValueError:
      await message.reply("Пожалуйста введите корректную цену.")

@dp.message_handler(lambda message: message.text == "Удалить актив")
async def remove_stock_prompt(message: types.Message):
  await message.reply("Введите символ актива для удаления:\n\nЧтобы вернуться назад в меню 'Мой портфель', нажмите 'Назад'.", reply_markup=back_button())
  
  # Устанавливаем состояние для удаления актива.
  await dp.current_state(user=message.from_user.id).set_state("removing_stock")

@dp.message_handler(state="removing_stock", content_types=types.ContentTypes.TEXT)
async def remove_stock(message: types.Message):
  stock_symbol=message.text.strip().upper()  

  telegram_id=message.from_user.id 
  user=get_user(telegram_id)

  if user:
      user_id=user[0] 
      portfolio_items=get_portfolio(user_id)

      # Проверяем наличие актива в портфеле перед удалением.
      if any(item[2] == stock_symbol for item in portfolio_items):
          remove_stock_from_portfolio(user_id ,stock_symbol) 
          await message.reply(f"Акция {stock_symbol} удалена из вашего портфеля.")
      else:
          await message.reply(f"Акция {stock_symbol} не найдена в вашем портфеле.")
      # Сбрасываем состояние после удаления актива.
      await dp.current_state(user=message.from_user.id).reset_state(with_data=False)

@dp.message_handler(lambda message: message.text == "Назад в главное меню")
async def back_to_main_menu(message: types.Message):
  await send_welcome(message)

@dp.message_handler(lambda message: message.text == "Назад")
async def back_to_previous_step(message: types.Message):
     # Возвращаемся к меню портфеля.
     await portfolio_menu(message)

def back_button():
     markup_back_portfolio_menu=ReplyKeyboardMarkup(resize_keyboard=True) 
     button_back_to_portfolio_menu=KeyboardButton("Назад") 
     
     markup_back_portfolio_menu.add(button_back_to_portfolio_menu)  
     return markup_back_portfolio_menu

def currency_back_button():
     markup_currency_back_menu=ReplyKeyboardMarkup(resize_keyboard=True) 
     button_return_to_main_menu=KeyboardButton("Возврат в главное меню")  
     
     markup_currency_back_menu.add(button_return_to_main_menu)  
     return markup_currency_back_menu

# Обработчик кнопки "Возврат в главное меню"
@dp.message_handler(lambda message: message.text == "Возврат в главное меню")
async def return_to_main_menu(message: types.Message):
     await send_welcome(message)

# Запуск бота
if __name__ == '__main__':
     executor.start_polling(dp ,skip_updates=True)