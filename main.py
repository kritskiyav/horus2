from aiohttp import web  # основной модуль aiohttp
import jinja2  # шаблонизатор jinja2
import aiohttp_jinja2  # адаптация jinja2 к aiohttp
from aiohttp_session import setup,SimpleCookieStorage
import sqlite3
from datetime import datetime
import gunicorn
import os

from app.parservk.settings import log_settings as l_set
from app.parservk.settings import db_settings as db_set

# в этой функции производится настройка url-путей для всего приложения
def setup_routes(application):
   from app.parservk.routes import setup_routes as setup_parservk_routes
   setup_parservk_routes(application)  # настраиваем url-пути приложения parservk

def setup_external_libraries(application: web.Application) -> None:
   # указываем шаблонизатору, что html-шаблоны надо искать в папке templates
   aiohttp_jinja2.setup(application, loader=jinja2.FileSystemLoader("templates"))

def check_sqlite_dbase():
   sqlite_connection = sqlite3.connect(db_set['db']['name'])
   cursor = sqlite_connection.cursor()
   query = r"SELECT name FROM sqlite_master WHERE type='table' AND name=?"
   cursor.execute(query, (db_set['table']['name'],))
   record = cursor.fetchall()

   if not record:
      sqlite_create_table_query = f'''CREATE TABLE {db_set['table']['name']} 
         (id INT PRIMARY KEY,
         ticket TEXT NOT NULL,
         date_create TEXT NOT NULL,
         completed TEXT,
         deployed TEXT);'''

      cursor.execute(sqlite_create_table_query)

      with open(l_set['db']['name'],'a',encoding="utf-8") as f:
         f.write(str(datetime.today())
            +f': таблица {db_set["table"]["name"]} '
            +f'создана в {db_set["db"]["name"]}\n')

      record = True
      sqlite_connection.commit()

   else:
      with open(l_set['db']['name'],'a',encoding="utf-8") as f:
         f.write(str(datetime.today())
            +f': подключены к {db_set["table"]["name"]}\n')

   cursor.close()


def setup_app(application):
   # настройка всего приложения состоит из:
   setup_external_libraries(application)  # настройки внешних библиотек, например шаблонизатора
   setup_routes(application)  # настройки роутера приложения
   setup(application, SimpleCookieStorage()) # настройка aiohttp-session
   check_sqlite_dbase()

env_port = 8080 if os.environ.get('PORT', None) is None else os.environ.get('PORT')

my_app = web.Application()  # создаем наш веб-сервер
setup_app(my_app)

if __name__ == '__main__':   
   web.run_app(my_app, port=env_port)

#if __name__ == "__main__":  # эта строчка указывает, что данный файл можно запустить как скрипт
   #setup_app(app)  # настраиваем приложение
   #web.run_app(app)  # запускаем приложение