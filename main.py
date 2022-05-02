import requests
import sqlite3
import telebot
import imgkit
# import os

from bs4 import BeautifulSoup
#from html2image import Html2Image
from config import TOKEN
from telebot import types

# my_dir = os.path.dirname(__file__)
# wkhtmltoimage_path = os.path.join(my_dir + '/bin/', 'wkhtmltoimage')
# config = imgkit.config(wkhtmltoimage=wkhtmltoimage_path)

SITE_URL = 'http://www.miu.by/rus/schedule/schedule.php'
URL_FOR_SHEDULE = 'http://miu.by/rus/schedule/shedule_load.php'
HEADERS_FOR_SHEDULE = {
    "Host": "www.miu.by",
    "Connection": "keep-alive",
    "User-Agent": "PostmanRuntime/7.28.3",
    "Content-type": "application/x-www-form-urlencoded",
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate",
}

HEADERS_FOR_PARSE = {
    'User-Agent': 'Mozilla/5.0'
}

BOT = telebot.TeleBot(TOKEN)

database = sqlite3.connect('TelegramData.db', check_same_thread=False)
cur = database.cursor()
cur.execute('''CREATE TABLE IF NOT EXISTS tgdata
               (tgid integer , miuGroup text)''')
database.commit()


def get_number_this_week():
    html = requests.get(SITE_URL, headers=HEADERS_FOR_PARSE)
    soup = BeautifulSoup(html.content, 'html.parser')
    string_with_number_week = soup.select('#printpage > span:nth-child(6)')[0]
    return int(string_with_number_week.text.split(' ')[-1])


def get_site_html(group, number_week):
    """Английская буква 'c' не работает, нужна русская. Делаем проверку"""
    if group[-1] == 'c':
        group = ''.join(group[0:6] + 'с')
        return requests.post(
            URL_FOR_SHEDULE,
            headers=HEADERS_FOR_SHEDULE,
            data={'week': number_week, 'group': group},
        )
    else:
        return requests.post(
            URL_FOR_SHEDULE,
            headers=HEADERS_FOR_SHEDULE,
            data={'week': number_week, 'group': group},
        )


def parse_web_site(group, number_week):
    html = get_site_html(group, number_week)
    if html.ok:
        schedule = html.text.split('<br>')[1]
        schedule = schedule[:72] + 'zoom:220%;' + schedule[72:]
        return imgkit.from_string(schedule, False)
        #Html2Image().screenshot(html_str=schedule, save_as='red_page.png')
    elif IndexError:
        return Exception
    else:
        return ConnectionError


def buttons():
    markup = types.InlineKeyboardMarkup(row_width=2)
    item1 = types.InlineKeyboardButton("Текущая неделя", callback_data='thisweek')
    item2 = types.InlineKeyboardButton("Следующая неделя", callback_data='nextweek')
    markup.add(item1, item2)
    return markup


@BOT.message_handler(commands=['start'])
def start_message(message):
    BOT.send_message(message.chat.id, 'Введите номер вашей группы')


@BOT.message_handler(commands=['deletedata'])
def delete_data(message):
    cur.execute(f"DELETE FROM tgdata WHERE tgid = '{message.chat.id}'")
    database.commit()
    BOT.send_message(message.chat.id, "Ваш номер группы удалён, введите его заново")


@BOT.message_handler(content_types=['text'])
def message(message):
    try:
        if parse_web_site(message.text, get_number_this_week()) == ConnectionError:
            BOT.send_message(message.chat.id, 'Сайт временно не доступен.')
        else:
            if message.chat.type == 'private':
                buttons()
                BOT.send_message(message.chat.id, 'выбор недели', reply_markup=buttons())
                cur.execute(f"SELECT tgid FROM tgdata WHERE tgid = '{message.chat.id}'")
                if cur.fetchone() is None:
                    cur.execute(f"INSERT INTO tgdata VALUES(?, ?)", (message.chat.id, message.text))
                    database.commit()
    except Exception:
        cur.execute(f"DELETE FROM tgdata WHERE tgid = '{message.chat.id}'")
        BOT.send_message(message.chat.id,
                         "Такой группы не существует. "
                         "Введите данные ещё раз")


@BOT.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        try:
            if call.data == "thisweek":
                for value in cur.execute(f"SELECT miuGroup FROM tgdata WHERE tgid = '{call.message.chat.id}'"):
                    img = parse_web_site(str(value[0]), get_number_this_week())
                    #open('red_page.png', 'rb')
                    BOT.send_photo(call.message.chat.id, img, reply_markup=buttons())
            if call.data == "nextweek":
                for value in cur.execute(f"SELECT miuGroup FROM tgdata WHERE tgid = '{call.message.chat.id}'"):
                    img = parse_web_site(str(value[0]), get_number_this_week() + 1)
                    #open('red_page.png', 'rb')
                    BOT.send_photo(call.message.chat.id, img, reply_markup=buttons())
        except Exception:
            BOT.send_message(call.message.chat.id,
                             'Похоже неделя ещё недоступна (могут быть проблемы с сайтом), повторите ввод или попробуйте позже',
                             reply_markup=buttons())


BOT.infinity_polling(timeout=10, long_polling_timeout = 5)
#BOT.polling(none_stop=True)