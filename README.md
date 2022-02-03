# Horus2
Сайт на aiohttp + aiosqlite, для автоматизации поиска людей в ВК с помощью подготовленных CSV файлов

После отправки пользователем CSV файла с данными о людях, которыъ необходимо найти, запускается асинхронная задача
которая с помощью aiohttp осуществляет запросы к социальной сети ВКонтакте и формирует итоговую таблицу с найденными людьми

Серверная часть так же обработана aiohttp+gunicorn.
БД: sqlite + aiosqlite.

Временный адрес сайта: https://horus2.herokuapp.com
