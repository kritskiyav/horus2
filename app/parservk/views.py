# асинхронная библиотека для sqlite3
import aiosqlite
# асинхронные запросы и jinja для templates
import aiohttp_jinja2
from aiohttp import web
# сессии для aiohttp
from aiohttp_session import get_session
# буквы, числа и рандом для генерации тикета
from string import ascii_uppercase, digits
from random import choice
from datetime import datetime
from settings import log_settings as l_set


# создаем функцию, которая будет отдавать html-файл
@aiohttp_jinja2.template("index.html")
async def index(request):
   return {'title': 'Пишем первое приложение на aiohttp'}

# вьюшка которая показывает сгенерированный билет
# при удачной загрузке файла в index_post
@aiohttp_jinja2.template("ticket.html")
async def ticket(request):
   session = await get_session(request)
   ticket = session['ticket']
   return {'ticket': ticket}

@aiohttp_jinja2.template("index_post.html")
async def index_post(request):
   # получаем файл от пользователя
   reader = await request.multipart()
   field = await reader.next()   
   assert field.name == 'csv'
   filename = field.filename

   # из за возможности отправки файлов большого объема
   # получаем файл частями(чанками)
   size = 0
   with open('temp/'+filename, 'wb') as f:
       while True:
           chunk = await field.read_chunk()  # 8192 bytes by default.
           if not chunk:
               break
           size += len(chunk)
           f.write(chunk)

   # получаем адрес куда редиректить пользователя
   # с полученным тикетом
   location = request.app.router['ticket'].url_for()

   # генерируем тикет
   ticket = ''
   for _ in range(10):
      ticket += str( (choice(ascii_uppercase), choice(digits))[choice([0,1])] )

   # записываем тикет в сессию пользователя
   session = await get_session(request)
   session['ticket'] = ticket

   # записываем тикет в БД
   async with aiosqlite.connect('test_sqlite.db') as db:
      query = '''INSERT INTO "ticket_tdb" 
               (ticket, date_create, completed, deployed)
               VALUES(?,?,0,0);'''
      await db.execute(query, (ticket, str(datetime.today())))
      await db.commit()
   # запись в log о добавлении тикета в БД
   with open(l_set['db']['name'], 'a') as f:
      f.write(f'{str(datetime.today())}: внесена запись с тикетом {ticket}\n')
   
   raise web.HTTPFound(location=location)