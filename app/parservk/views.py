# асинхронная библиотека для sqlite3
import aiosqlite
# загрузка asyncio
import asyncio
# загрузка асинхронной работы с файлами
from aiofile import async_open
# асинхронные запросы и jinja для templates
import aiohttp_jinja2
import aiohttp
from aiohttp import web
# сессии для aiohttp
from aiohttp_session import get_session
# буквы, числа и рандом для генерации тикета
from string import ascii_uppercase, digits
from random import choice
from datetime import datetime
# загрузка внутренних модулей проекта
# from app.parservk.settings import log_settings as l_set # импорт настроек во вьюшки
from app.parservk.settings import db_settings as db_set  # импорт настроек во вьюшки
from app.parservk.settings import search_settings as srch_set  # импорт настроек во вьюшки
# загрузка модулей для обработки/парсинга страниц
import csv
from bs4 import BeautifulSoup as bs
import re
# импорт шаблонизатора для формирования ответной страницы
import jinja2

import os
import time


@aiohttp_jinja2.template("index.html")
async def index(request):
    '''главная странца'''
    return {'title': 'HORUSKA'}

@aiohttp_jinja2.template("ticket.html")
async def ticket(request):
    '''вьюшка которая показывает сгенерированный билет
    при удачной загрузке файла в index_post'''
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

    # генерируем тикет
    ticket = ''
    for _ in range(10):
        ticket += str((choice(ascii_uppercase), choice(digits))[choice([0, 1])])

    # из за возможности отправки файлов большого объема
    # получаем файл частями(чанками)
    size = 0
    with open(f'temp/{ticket}.csv', 'wb') as f:
        while True:
            chunk = await field.read_chunk()  # 8192 bytes by default.
            if not chunk:
                break
            size += len(chunk)
            f.write(chunk)

    # получаем адрес куда редиректить пользователя
    # с полученным тикетом
    location = request.app.router['ticket'].url_for()

    # записываем тикет в сессию пользователя
    session = await get_session(request)
    session['ticket'] = ticket

    # записываем тикет в БД
    async with aiosqlite.connect(db_set['db']['name']) as db:
        query = f'''INSERT INTO "{db_set['table']['name']}" 
               (ticket, date_create, completed, deployed)
               VALUES(?,?,0,0);'''
        await db.execute(query, (ticket, str(datetime.today())))
        await db.commit()
    # запись в log о добавлении тикета в БД
    print(f'{str(datetime.today())}: внесена запись с тикетом {ticket} ')

    # await asyncio.gather(read_ticket_csv(ticket))
    # loop = asyncio.get_event_loop()
    asyncio.ensure_future(read_ticket_csv(ticket))
    raise web.HTTPFound(location=location)

async def read_ticket_csv(ticket):
    '''Функция считывает пользовательский csv файл и формирует список для поиска'''
    await asyncio.sleep(0)
    # пробуем найти кодировку присланного файла
    my_enc = 'utf-8'
    try:
        afp = open(f'temp/{ticket}.csv', encoding=my_enc)
        for line in afp:
            temp = line.rstrip().split(',')
            break
    except UnicodeDecodeError:
        my_enc = 'cp1251'
    finally:
        print(f'{str(datetime.today())}: для тикета {ticket} выбрана кодировка {my_enc}')
    # открываем файл ticket.csv
    with open(f'temp/{ticket}.csv', encoding=my_enc) as afp:
        find_list = []
        # формируем лист(список) фамилий
        for line in afp:
            temp = line.rstrip().split(',')
            if len(temp) == 2:
                find_list.append((temp[0], temp[1]))
                # передаем управление, что бы не блокировать другие функции
                await asyncio.sleep(0)
    find_list = tuple(find_list)
    # запускаем корутину по поиску
    # await asyncio.gather(find_people_from_tuple(find_list, ticket))
    asyncio.create_task(find_people_from_tuple(find_list, ticket))

async def find_people_from_tuple(peoples: tuple, ticket):
    '''Функция получает tuple с людьми для поиска и формирует списки задач по поиску'''
    time_start = time.time()
    res = []
    print(f'{str(datetime.today())}: приступил к работе над тикетом {ticket}')

    # подключаемся к одноклассникам, получаем сессию и bci
    ok_conn_res = await asyncio.gather(connect_to_ok())
    ok_session, ok_cookies, ok_params = ok_conn_res[0]

    # создаем список задач
    task_list = []
    search_progress = 0

    # перебираем список людей, которых нужно найти
    for i, people in enumerate(peoples):
        # создаем задачу и добавляем её в список задач
        task_list.append(asyncio.create_task(search_people(people,ok_session, ok_cookies, ok_params)))
        # если задач 13 или список подошел к концу
        if len(task_list) == srch_set['task_list_size'] or i == len(peoples)-1:
            # запускаем задачи и await-им их выполнение, результаты выполнения будет в списке
            task_result_list = await asyncio.gather(*task_list)
            search_progress += len(task_list)
            print(f'''{str(datetime.today())}: обработано {search_progress} из {len(peoples)} в тикете {ticket}''')
            # обнуляем список задач
            task_list = []
            # добавляем результаты к общему списку
            for tusk_result in task_result_list:
                res.extend(tusk_result)

    # закрываем сессию с ОК
    await ok_session.close()

    # формируем html результат
    create_result = await asyncio.gather(create_output_file(ticket, res))
    if create_result[0]['result']:
        print(f'{str(datetime.today())}: создан файл {create_result[0]["fname"]}')

        # вносим изменения в базу, помечаем тикет выполненным
        async with aiosqlite.connect(db_set['db']['name']) as db:
            query = f'''UPDATE "{db_set['table']['name']}" 
                   SET completed = "1"
                   WHERE ticket = ?'''
            await db.execute(query, (ticket,))
            await db.commit()

        print(f'{str(datetime.today())}: тикет {ticket} помечен как выполненный')
        time_start = time.time()-time_start
        print(f'{str(datetime.today())}: тикет {ticket} выполнялся {round(time_start//60,0)} мин. {round(time_start%60,2)} сек.')

async def create_output_file(ticket, res):
    '''получает итоговый результат поиска и номер тикета
    формирует html файл для выдачи пользователю'''

    templateLoader = jinja2.FileSystemLoader(searchpath="templates/")
    templateEnv = jinja2.Environment(loader=templateLoader)
    TEMPLATE_FILE = "result.html"
    template = templateEnv.get_template(TEMPLATE_FILE)
    outputText = template.render(ticket=ticket, result_list=res)

    async with async_open(f'temp/output_{ticket}.html', 'w') as f:
        await f.write(outputText)

    return {'result':True,'fname': f'temp/output_{ticket}.html'}

async def search_people(people,ok_session, ok_cookies, ok_params):
    '''функция получает одного человека (ФИО и ДР), создает и запускает задачи
    по поиску человека в ВК и ОК, и возвращает результат в виде списка'''

    search_result = []

    name = '%20'.join(people[0].split())
    bday, bmonth, byear = people[1].split('.')

    # создаем задачу по поиску человека в ОК
    ok_task = asyncio.create_task(search_in_ok(ok_session, ok_cookies, ok_params,
                                               name=name, bday=bday, bmonth=bmonth, byear=byear))
    # создаем задачу по поиску человека в ВК
    vk_task = asyncio.create_task(search_in_vk(name, bday, bmonth, byear))
    # запускаем задачи на выполнение, await-им результат
    task_result = await asyncio.gather(ok_task,vk_task)
    # перебираем результаты
    for result in task_result:
        # если тип результата list, добавляем в итоговый ответ
        if type(result) == list:
            search_result.extend(result)

    return search_result

async def search_in_vk(name,bday, bmonth, byear):
    '''функция поиска человека в вконтакте
    отправляет запрос и парсит результат'''
    query = ('https://vk.com/search?c%5B' +
             f'bday%5D={bday}&c%5B' +
             f'bmonth%5D={bmonth}&c%5B' +
             f'byear%5D={byear}&c%5B' +
             'name%5D=1&c%5B' +
             'per_page%5D=40&c%5B' +
             f'q%5D={name}&c%5B' +
             'section%5D=people')
    async with aiohttp.ClientSession() as session:
        async with session.get(query) as resp:
            html_text = str(await resp.text())

    soup = bs(html_text, 'html.parser')
    a = (soup.find_all('div', 'si_body'))
    b = (soup.find_all('div', 'Avatar__image Avatar__image-1'))
    c = (soup.find_all('a', 'simple_fit_item search_item'))
    d = (soup.find_all('div', 'si_body'))

    name_reg = r'>\w+\s*\w*<'
    ava_reg = r'''url\('.+'\)\"'''
    ava_fix_path = r'amp;'
    vk_start_url = 'https://vk.com'
    res = []
    for sname, sava, surl, sdata in zip(a, b, c, d):
        name = re.search(name_reg, str(sname))
        if not name is None:
            name = name[0][1:-1]
        else:
            name = 'ОШИБКА ПОИСКА'

        ava = re.search(ava_reg, str(sava))
        if not name is None:
            ava = ava[0][5:-3]
        else:
            name = '$ОШИБКА ПОИСКА'

        if ava[0] == '/':
            ava = vk_start_url + ava
        elif ava[0] != '$':
            re.sub(ava_fix_path, '', ava)

        url = vk_start_url + surl['href']
        data = ','.join([i.get_text() for i in sdata.find_all('div', 'si_slabel')])
        res.append((ava, name, url, data))

    return res

async def connect_to_ok():
    '''Функция подключения к одноклассникам и получения сессии'''
    query = 'https://ok.ru'
    async with aiohttp.ClientSession() as session:
        async with session.get(query) as resp:
            user_bci = resp.headers['Set-Cookie'].split('; ')[0].split('=')[1]

    with open('app/parservk/ok_settings') as f:
        pswd = f.read().rstrip()

    query = 'https://ok.ru/dk?cmd=AnonymLogin&st.cmd=anonymLogin'
    params = {'st.email': 'kritskiyav',
            'st.password': pswd,
            'st.posted': 'set'}
    cookies = dict(bci=user_bci)
    session = aiohttp.ClientSession(cookies=cookies)
    resp = await session.post(query, params=params)
    print(f'{str(datetime.today())}: подключение к Одноклассникам, статус: {resp.status==200}')

    # Возвращаем сессию и необходимые данные
    return session,cookies,params

async  def search_in_ok(session,cookies,params,**human):
    '''функция поиска человека в одноклассниках
    отправляет запрос и парсит результат'''

    query = (f'https://ok.ru/dk' +
           '?st.cmd=searchResult' +
           '&st.mode=Users' +
           f'&st.bthYear={human["byear"]}' +
           f'&st.bthMonth={str(int(human["bmonth"])-1)}' +
           f'&st.query={human["name"]}' +
           '&st.grmode=Groups' +
           f'&st.bthDay={human["bday"]}' +
           '&st.mmode=Track')

    async with session.get(query, params=params) as resp:
        html_text = await resp.text()

    soup = bs(html_text, 'html.parser')
    a = (soup.find_all('div', 'row__px8cs skip-first-gap__m3nyy'))

    name_pattern = r'(?<=\"query\":\")\w+\s+\w+'
    profile_pattern = r'(?<=href=\")/.+?/.+?(?=\")'
    ava_pattern = r'(?<=src=\")/.+?/.+?(?=&amp)'
    info_pattern = r'(?<=div class=\"card-info).+?>\w.+?</div>'

    res = []
    for item in a:
        name = re.search(name_pattern, str(item))
        if name is None:
            name = 'ОШИБКА ПОИСКА'
        else:
            name = name[0]

        url = re.search(profile_pattern, str(item))
        if url is None:
            url = 'ОШИБКА ПОИСКА'
        else:
            url = 'https://ok.ru' + url[0]

        ava = re.search(ava_pattern, str(item))
        if ava is None:
            ava = ('https://vk.com/images/camera_50.png')
        else:
            ava = ava[0]

        data = re.search(info_pattern, str(item))
        if data is None:
            data = 'ОШИБКА ПОИСКА'
        else:
            data = data[0][9:]
            data = re.sub(r'\s',' ',data)
        res.append((ava, name, url, data))
        await asyncio.sleep(0)
    return res

@aiohttp_jinja2.template("ticket_get.html")
async def ticket_get(request):
    '''Выводит форму для получение ticket-a и показывает статус обработки
    всех имеющихся тикетов'''
    async with aiosqlite.connect(db_set['db']['name']) as db:
        query = f'''SELECT ticket, completed FROM {db_set['table']['name']}'''
        result_list = []
        session_ticket = await get_session(request)
        async with db.execute(query) as cursor:
            async for row in cursor:
                if row:
                    if session_ticket['ticket'] == row[0] and row[1] == '1':
                        file = await asyncio.gather(get_result_for_ticket(session_ticket['ticket']))
                        return web.Response(text=file[0], content_type='text/html')
                    text = '*'*(len(row[0])-4)+row[0][-4:]
                    result_list.append((text, 'Готов' if int(row[1]) else 'В работе'))
    return {'result_list': result_list}

@aiohttp_jinja2.template("ticket_post.html")
async def ticket_post(request):
    '''вьюшка просматривает отправленный пользователем тикет и в случае
    выполнения тикета выдает результат, иначе обновляет страницу'''

    data = await request.post()
    user_ticket = data['ticket']
    # проверяем выполнен ли тикет в базе
    row = ''
    async with aiosqlite.connect(db_set['db']['name']) as db:
        query = f'''SELECT completed FROM "{db_set['table']['name']}" 
               WHERE ticket = ?'''
        async with db.execute(query, (user_ticket,)) as cursor:
            async for row in cursor:
                res = row
                break
    print(f'{str(datetime.today())}: {user_ticket} статус: {("В работе","Выполнено")[int(row[0])]}')

    # если тикет выполнен - выдаем результат
    if row and row[0] == '1':
        file = await asyncio.gather(get_result_for_ticket(user_ticket))
        return web.Response(text=file[0], content_type='text/html')
    # иначе - обновляем страницу
    else:
        location = request.app.router['ticket_get'].url_for()
        raise web.HTTPFound(location=location)

async def get_result_for_ticket(user_ticket):
    '''функция получает тикет, чистит базу, выдает результат и удаляет рабочие файлы'''

    async with aiosqlite.connect(db_set['db']['name']) as db:
        query = f'''DELETE FROM "{db_set['table']['name']}" 
              WHERE ticket = ?'''
        cursor = await db.execute(query, (user_ticket,))
        await db.commit()
    print(f'{str(datetime.today())}: удалена запись с тикетом {user_ticket}')
    async with async_open(f'temp/output_{user_ticket}.html') as f:
        file = await f.read()
    os.remove(f'temp/output_{user_ticket}.html')
    os.remove(f'temp/{user_ticket}.csv')

    return file

@aiohttp_jinja2.template("help.html")
async def help(request):
    return None