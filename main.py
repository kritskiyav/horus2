from aiohttp import web  # основной модуль aiohttp
import jinja2  # шаблонизатор jinja2
import aiohttp_jinja2  # адаптация jinja2 к aiohttp
from aiohttp_session import setup,SimpleCookieStorage
import sqlite3
from datetime import datetime

from app.parservk.settings import log_settings as l_set

# в этой функции производится настройка url-путей для всего приложения
def setup_routes(application):
   from app.parservk.routes import setup_routes as setup_parservk_routes
   setup_parservk_routes(application)  # настраиваем url-пути приложения parservk

def setup_external_libraries(application: web.Application) -> None:
   # указываем шаблонизатору, что html-шаблоны надо искать в папке templates
   aiohttp_jinja2.setup(application, loader=jinja2.FileSystemLoader("templates"))

def check_sqlite_dbase():
   sqlite_connection = sqlite3.connect('main_sqlite.db')
   cursor = sqlite_connection.cursor()
   query = r"SELECT name FROM sqlite_master WHERE type='table' AND name='ticket_tdb'"
   cursor.execute(query)
   record = cursor.fetchall()
   if not record:
      sqlite_create_table_query = '''CREATE TABLE ticket_tdb (
         id INTEGER PRIMARY KEY,
         ticket TEXT NOT NULL,
         date_create TEXT NOT NULL,
         completed TEXT,
         deployed TEXT);'''
      cursor.execute(sqlite_create_table_query)
      with open(l_set['db']['file_name'],'a') as f:
         f.write(str(datetime.today())+': таблица ticket_tdb создана в main_sqlite.db\n')
      record = True
      sqlite_connection.commit()
   else:
      with open(l_set['db']['file_name'],'a') as f:
         f.write(str(datetime.today())+': подключены к ticket_tdb\n')
   cursor.close()


def setup_app(application):
   # настройка всего приложения состоит из:
   setup_external_libraries(application)  # настройки внешних библиотек, например шаблонизатора
   setup_routes(application)  # настройки роутера приложения
   setup(application, SimpleCookieStorage()) # настройка aiohttp-session
   check_sqlite_dbase()

app = web.Application()  # создаем наш веб-сервер

if __name__ == "__main__":  # эта строчка указывает, что данный файл можно запустить как скрипт
   setup_app(app)  # настраиваем приложение
   web.run_app(app)  # запускаем приложение