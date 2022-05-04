import requests
import sqlite3
import telebot
import imgkit

from bs4 import BeautifulSoup
from config import TOKEN
from telebot import types


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


def write_data_in_db(message):
    delete_data_sql(message)
    cur.execute(f"INSERT INTO tgdata VALUES(?, ?)", (message.chat.id, message.text))
    database.commit()


def parse_web_site(data, number_week):
    if any(map(str.isdigit, data)):
        type_data = 'group'
    else:
        type_data = 'prep'
    # number_week = 25
    html = get_site_html(data, type_data, number_week)
    if html.ok:
        schedule = html.text.split('<br>')[1]
        schedule = schedule[:72] + 'zoom:220%;' + schedule[72:]
        return imgkit.from_string(schedule, False)
    elif IndexError:
        return Exception
    else:
        return ConnectionError


def get_site_html(data, type_data, number_week):
    return requests.post(
        URL_FOR_SHEDULE,
        headers=HEADERS_FOR_SHEDULE,
        data={'week': number_week, type_data: data},
    )


def handling_messages_with_group(message):
    """Английская буква 'c' не работает, нужна русская. Делаем проверку если вводится группа"""
    if message.text[-1] == 'c':
        message.text = ''.join(message.text[0:6] + 'с')
    html = get_site_html(message.text, 'search', get_number_this_week())
    if html.ok:
        soup = BeautifulSoup(html.text, 'html.parser')
        data = soup.find_all('a')
        links = [x.text.strip() for x in data]
        if len(links) > 1:
            BOT.send_message(message.chat.id, 'Вот несколько вариантов', reply_markup=search_suggestions_buttons(links))
            return False
        elif len(links) == 1:
            message.text = links[0]
            write_data_in_db(message)
            return True
        else:
            BOT.send_message(message.chat.id, 'Ничего не найдено, повторите ввод')
            delete_data_sql(message)
            return False
    elif IndexError:
        return Exception
    else:
        return ConnectionError


def search_suggestions_buttons(data):
    markup = types.InlineKeyboardMarkup(row_width=1)
    buttons = []
    for button in data:
        buttons.append(types.InlineKeyboardButton(button, callback_data=button))
    markup.add(*buttons)
    return markup


def buttons():
    markup = types.InlineKeyboardMarkup(row_width=2)
    item1 = types.InlineKeyboardButton("Текущая неделя", callback_data='thisweek')
    item2 = types.InlineKeyboardButton("Следующая неделя", callback_data='nextweek')
    markup.add(item1, item2)
    return markup


def selection_buttons():
    markup = types.InlineKeyboardMarkup(row_width=2)
    item1 = types.InlineKeyboardButton("Расписание группы", callback_data='shedule_std')
    item2 = types.InlineKeyboardButton("Расписание преподавателей", callback_data='shedule_teach')
    markup.add(item1, item2)
    return markup


@BOT.message_handler(commands=['start'])
def start_message(message):
    BOT.send_message(message.chat.id, 'Введите группу или фамилию преподавателя для получения расписания',
                     reply_markup=selection_buttons())


@BOT.message_handler(commands=['deletedata'])
def delete_data(message):
    delete_data_sql(message)
    delete_data_message(message)


def delete_data_sql(message):
    cur.execute(f"DELETE FROM tgdata WHERE tgid = '{message.chat.id}'")
    database.commit()


def delete_data_message(message):
    BOT.send_message(message.chat.id, "Информация удалена, введите новые данные для поиска",
                     reply_markup=selection_buttons())


@BOT.message_handler(content_types=['text'])
def message_handler(message):
    selection_buttons()
    is_change_week = handling_messages_with_group(message)
    if message.chat.type == 'private' and is_change_week:
        BOT.send_message(message.chat.id, 'выбор недели', reply_markup=buttons())


@BOT.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    if call.message:
        try:
            if call.data == "thisweek":
                for value in cur.execute(f"SELECT miuGroup FROM tgdata WHERE tgid = '{call.message.chat.id}'"):
                    img = parse_web_site(str(value[0]), get_number_this_week())
                    BOT.send_photo(call.message.chat.id, img, reply_markup=buttons())
            if call.data == "nextweek":
                for value in cur.execute(f"SELECT miuGroup FROM tgdata WHERE tgid = '{call.message.chat.id}'"):
                    img = parse_web_site(str(value[0]), get_number_this_week() + 1)
                    BOT.send_photo(call.message.chat.id, img, reply_markup=buttons())

            if call.data == "shedule_std":
                BOT.send_message(call.message.chat.id, "Введите номер группы", )
            if call.data == "shedule_teach":
                BOT.send_message(call.message.chat.id, "Введите Фамилию преподавателя", )

            if call.data not in ["thisweek", "nextweek", "shedule_std", "shedule_teach"]:
                call.message.text = call.data
                message_handler(call.message)

        except Exception:
            BOT.send_message(call.message.chat.id,
                             'Похоже неделя ещё недоступна, повторите ввод или попробуйте позже',
                             reply_markup=buttons())


BOT.infinity_polling(timeout=10, long_polling_timeout=5)
# BOT.polling(none_stop=True)
