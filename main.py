import os
import telebot
from telebot import types
import json
import shutil
import psycopg2
import datetime
import logging
from flask import Flask, request

admins = ['962211887', '415720787', '5629996816']

TOKEN = '5766023354:AAG5cbHs3fFtJFxO9VplTbXkqxMQm6xWRA0'
APP_URL = f'https://onlylabs.herokuapp.com/{TOKEN}'
bot = telebot.TeleBot(TOKEN)
db_con = psycopg2.connect(
    database="de68tv7tq8hv34",
    user="xjizawoqlhkpba",
    password="7d7a93892b2072a50cf7567ead3d5f2ae589c098be91d31a5cbe264b0d774489",
    host="ec2-54-76-43-89.eu-west-1.compute.amazonaws.com",
    port="5432")
db_cur = db_con.cursor()
server = Flask(__name__)
logger = telebot.logger
logger.setLevel(logging.DEBUG)


btn_menu = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True).add(types.KeyboardButton('Меню'))


def clear_bucket(id):
    with open(f'cookies/buckets/{id}.json', 'w') as bucket:
        json.dump({'count': 0, 'total': 0}, bucket)


def exists(id):
    db_cur.execute("SELECT client_id FROM clients")
    for client in db_cur.fetchall():
        if str(id) == client[0]:
            return False
    db_cur.execute("INSERT INTO clients(client_id) VALUES (%s)", (id,))
    db_con.commit()
    return True


def display_menu(id):
    users_kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    btn_labs = types.KeyboardButton("Лабы")
    btn_bucket = types.KeyboardButton("Корзина")
    btn_settings = types.KeyboardButton("Настройки")
    users_kb.add(btn_labs, btn_bucket).add(btn_settings)
    bot.send_message(id, 'Меню', reply_markup=users_kb)


def admin(id):
    admin_kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    subjects = types.KeyboardButton("Предметы")
    all_bd = types.KeyboardButton("Общая БД")
    single_bd = types.KeyboardButton("Личная БД")
    admin_kb.add(subjects, all_bd, single_bd)
    bot.send_message(id, "Меню", reply_markup=admin_kb)


def print_orders(id, file_name):
    with open(f'cookies/orders/{file_name}', 'r') as file:
        data = json.load(file)
        labs = 'Лабы:'
        for c in range(1, data['count'] + 1):
            c = str(c)
            labs += (f'\nПредмет: {data[c]["subject"]}\nНомер: {data[c]["lab"]}')
        db_cur.execute('SELECT variant FROM clients WHERE client_id = %s', (str(id),))
        variant = db_cur.fetchone()[0]
        return labs + f'\nВариант {variant}\nСтоимость {data["total"]}BYN'


@bot.message_handler(commands=['start'])
def start(message):
    id = message.chat.id
    if str(id) in admins:
        admin(id)
    else:
        if exists(id):
            bot.send_message(id,
                             "Здесь ты можешь выбрать предмет и лабу, которая тебе нужна, оплатить по ЕРИПУ стоимость лабы, и ждать свою лабу")
            bot.send_message(id, "Введи номер своего варианта(/var номер варианта, пример (/var 5))")
        else:
            bot.send_message(id, "Привет, давно тебя не видел")
            display_menu(id)
        clear_bucket(id)


@bot.message_handler(commands=['var'])
def enter_var(message):
    id = message.chat.id
    try:
        db_cur.execute('UPDATE clients SET variant = %s WHERE client_id = %s', (int(message.text.split()[1]), str(id),))
        db_con.commit()
        display_menu(id)
    except:
        bot.send_message(id, 'Ты что сделал не так (попробуй еще раз)')


@bot.message_handler(commands=['comment'])
def enter_commet(message):
    id = message.chat.id
    db_cur.execute('UPDATE orders SET comment = %s WHERE client_id = %s', (message.text[9:], str(id),))
    db_con.commit()
    bot.send_message(id, 'Комментарии будут учтены, теперь точно жду скриншот оплаты)')


@bot.message_handler(content_types=['photo'])
def send_payout(message):
    id = message.chat.id
    photo = message.photo[-1]
    file_id = photo.file_id
    file_path = bot.get_file(file_id).file_path
    downloaded_file = bot.download_file(file_path)
    name = file_id + '.jpg'
    new_file = open('cookies/screenshots/' + name, mode='wb')
    new_file.write(downloaded_file)
    new_file.close()
    db_cur.execute('SELECT file_name FROM orders WHERE client_id = %s', (str(id),))
    file_name = sorted(list(map(lambda x: x[0], db_cur.fetchall())), reverse=True)[0]
    with open(f'cookies/orders/{file_name}', 'r') as file:
        data = json.load(file)
        img = open('cookies/screenshots/' + name, mode='rb')
        bot.send_message(id, 'Жди пока Мы проверим платёж')
        display_menu(id)
        yes_btn = types.InlineKeyboardButton('✅', callback_data=f'YES {id} {file_name}')
        no_btn = types.InlineKeyboardButton('❌', callback_data=f'NO {id}')
        kb = types.InlineKeyboardMarkup().add(yes_btn, no_btn)
        bot.send_photo(5629996816, img)
        bot.send_message(5629996816, data['total'], reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data.startswith('YES'))
def true_payments(call):
    info = call.data.split()[1:]
    bot.delete_message(5629996816, call.message.message_id)
    bot.delete_message(5629996816, call.message.message_id - 1)
    db_cur.execute('UPDATE orders SET payment = %s WHERE file_name = %s', (True, info[1]))
    db_con.commit()
    bot.send_message(info[0], 'Платёж подтвержден, жди пока мы все сделаем)')
    clear_bucket(info[0])
    orders = print_orders(info[0], info[1])
    with open(f'cookies/orders/{info[1]}', 'r') as file:
        data = json.load(file)
        db_cur.execute('INSERT INTO work_lab(client_id, file_name, price) VALUES(%s, %s, %s)',
                       (str(info[0]), info[1], data['total']))
        db_con.commit()
    with open(f'cookies/current_orders/{info[1]}', 'w') as id:
        data = {}
        for a in admins:
            btn = types.InlineKeyboardButton('Взять', callback_data=f'{a} {info[0]} {info[1]}')
            kb = types.InlineKeyboardMarkup().add(btn)
            data[a] = (bot.send_message(a, orders, reply_markup=kb)).message_id
        json.dump(data, id)


@bot.callback_query_handler(func=lambda call: call.data.split()[0] in admins)
def get_order(call):
    id = call.message.chat.id
    client = call.data.split()[1]
    file_name = call.data.split()[2]
    btn = types.InlineKeyboardButton('✅Взял', callback_data='123')
    kb = types.InlineKeyboardMarkup().add(btn)
    bot.edit_message_text(chat_id=id, message_id=call.message.message_id, text=call.message.text, reply_markup=kb)
    db_cur.execute('UPDATE work_lab SET "%s" = true WHERE file_name = %s', (id, file_name))
    db_con.commit()
    with open(f'cookies/current_orders/{file_name}', 'r') as file:
        data = json.load(file)
        for a in admins:
            bot.delete_message(a, data[a])
    os.remove(f'cookies/current_orders/{file_name}')


@bot.callback_query_handler(func=lambda call: call.data.startswith('NO'))
def false_payments(call):
    bot.delete_message(5629996816, call.message.message_id)
    bot.delete_message(5629996816, call.message.message_id - 1)
    bot.send_message(call.data.split()[1], 'Платеж не потдвержден, напиши сюда @LabsHub')


@bot.message_handler(content_types=['text'])
def god_func(message):
    id = message.chat.id
    if str(id) in admins:
        if message.text == 'Предметы':
            sub_inl = types.InlineKeyboardMarkup()
            btn_sub = types.InlineKeyboardButton("Добавить предмет", callback_data='subject')
            btn_lab = types.InlineKeyboardButton("Добавить лабу", callback_data='lab')
            sub_inl.add(btn_sub, btn_lab)
            bot.send_message(id, "Выбери", reply_markup=sub_inl)
        elif message.text == 'Общая БД':
            db_cur.execute(
                'SELECT client_id, file_name FROM work_lab WHERE "%s" = false AND "%s" = false AND "%s" = false',
                (int(admins[0]), int(admins[1]), int(admins[2])))
            labs = db_cur.fetchall()
            if labs:
                with open(f'cookies/{id}.json', 'w') as file:
                    btn = types.KeyboardButton('Назад')
                    kb = types.ReplyKeyboardMarkup(resize_keyboard=True).add(btn)
                    data = {}
                    data['count'] = len(labs)
                    data['start'] = bot.send_message(id, 'Упал, отжался, выбрал лабу и пошел ебашить',
                                                     reply_markup=kb).message_id
                    for i in range(len(labs)):
                        btn = types.InlineKeyboardButton('Взять', callback_data=f'{id} {labs[i][0]} {labs[i][1]}')
                        kb = types.InlineKeyboardMarkup().add(btn)
                        data[f'{i}'] = bot.send_message(id, print_orders(labs[i][0], labs[i][1]),
                                                        reply_markup=kb).message_id
                    json.dump(data, file)
            else:
                bot.send_message(id, 'Никому больше не нужны лабы(((((((((((')
                admin(id)
        elif message.text == 'Личная БД':
            db_cur.execute('SELECT client_id, file_name FROM work_lab WHERE "%s" = true', (id,))
            labs = db_cur.fetchall()
            if labs:
                for lab in labs:
                    btn = types.InlineKeyboardButton('Сделано', callback_data=f'complete {lab[0]} {lab[1]}')
                    kb = types.InlineKeyboardMarkup().add(btn)
                    bot.send_message(id, print_orders(lab[0], lab[1]), reply_markup=kb)
            else:
                bot.send_message(id, 'Лентяй, иди работать')
        elif message.text == 'Назад':
            with open(f'cookies/{id}.json', 'r') as file:
                data = json.load(file)
                bot.delete_message(id, data['start'])
                for i in range(data['count']):
                    bot.delete_message(id, data[f'{i}'])
                admin(id)
        else:
            if message.text[0] == '#':
                info = (message.text[1:]).split(' ')
                num, price = info[0], float(info[1])
                subject = 0
                with open(f'cookies/{message.chat.id}.json', 'r') as read_file:
                    subject = int(json.load(read_file)['subject'])
                db_cur.execute('SELECT lab FROM "%s"', (subject,))
                if num not in [i[0] for i in db_cur.fetchall()]:
                    db_cur.execute('INSERT INTO "%s" (lab, price) VALUES(%s, %s)', (subject, num, price,))
                    bot.send_message(id, "Лаба добавлена")
                else:
                    db_cur.execute('UPDATE "%s" SET price = %s WHERE lab = %s', (subject, price, num,))
                    bot.send_message(id, "Цена на лабу обнавлена")
                db_con.commit()
                admin(id)
            else:
                db_cur.execute("SELECT * FROM subjects")
                count = len(db_cur.fetchall()) + 1
                db_cur.execute(
                    'CREATE TABLE "%s" (id serial constraint  "%s_pk" primary  key, lab varchar(15), price float);',
                    (count, count))
                db_con.commit()
                db_cur.execute("INSERT INTO subjects(subject, subject_output) VALUES(%s, %s)", (count, message.text,))
                db_con.commit()
                bot.send_message(id, 'Предмет добавлен')
                admin(id)
    else:
        if message.text == 'Лабы':
            inl_sub = types.InlineKeyboardMarkup()
            db_cur.execute('SELECT * FROM subjects')
            subjects = db_cur.fetchall()
            if subjects:
                for subject in subjects:
                    inl_sub.add(types.InlineKeyboardButton(f"{subject[1]}", callback_data=f"usub {subject[0]}"))
                bot.send_message(id, "Выбери предмет", reply_markup=inl_sub)
            else:
                bot.send_message(id, "Прости, но лаб пока что нет(")
                display_menu(id)
        elif message.text == 'Корзина':
            try:
                with open(f'cookies/buckets/{id}.json', 'r') as read_file:
                    data = json.load(read_file)
                    if data['count'] > 0:
                        db_cur.execute(f'SELECT variant FROM clients WHERE client_id = %s', (str(id),))
                        variant = db_cur.fetchone()[0]
                        for c in range(1, data['count'] + 1):
                            c = str(c)
                            bot.send_message(id,
                                             f"Предмет: {data[c]['subject']}\nЛаба: №{data[c]['lab']}\nВариант: {variant}\nЦена: {data[c]['price']}")
                        buy_btn = types.InlineKeyboardButton('Всё хорошо', callback_data='good')
                        clear_btn = types.InlineKeyboardButton('Очистить', callback_data='clear')
                        kb = types.InlineKeyboardMarkup().add(buy_btn, clear_btn)
                        bot.send_message(id,
                                         'Если все правильно нажимай кнопку "Всё хорошо" или кнопку "Очистить" если что-то неправильно',
                                         reply_markup=kb)
                    else:
                        bot.send_message(id, 'Твоя корзина пуста(')
                        display_menu(id)
            except:
                bot.send_message(id, 'Твоя корзина пуста(')
                display_menu(id)
        elif message.text == 'Меню':
            display_menu(id)
        elif message.text.lower() == 'юра лох':
            bot.send_message(id, 'Согласен')
            display_menu(id)
        else:
            bot.send_message(id, 'Хватит писать фигню, я тебя забаню!!!!!!')
            display_menu(id)


def check_bucket(id, lab, output_subject):
    with open(f'cookies/buckets/{id}.json', 'r') as read_file:
        data = json.load(read_file)
        for c in range(1, data['count'] + 1):
            c = str(c)
            if data[c]['lab'] == lab and data[c]['subject'] == output_subject:
                return True
        return False


@bot.message_handler(content_types=['document'])
def get_document(message):
    id = message.chat.id
    file_info = bot.get_file(message.document.file_id)
    downloaded_file = bot.download_file(file_info.file_path)
    client_id = ''
    file_name = ''
    with open(f'cookies/{id}', 'r') as file:
        data = json.load(file)
        client_id = data['client_id']
        file_name = data['file_name']
    os.remove(f'cookies/{id}')
    with open(f'cookies/orders/{file_name}', 'r') as file:
        info = json.load(file)
        msg = 'Выполнен заказ:\n' + print_orders(client_id, file_name)
        bot.send_message(client_id, msg)
        bot.send_document(client_id, downloaded_file)
        display_menu(client_id)
        admin(id)
    db_cur.execute('UPDATE orders SET complete = %s WHERE file_name = %s', (True, file_name))
    db_cur.execute('DELETE FROM work_lab WHERE file_name = %s', (file_name,))
    db_con.commit()


@bot.callback_query_handler(func=lambda call: call.data.startswith('complete'))
def complete_lab(call):
    id = call.message.chat.id
    data = call.data.split()[1:]
    bot.delete_message(id, call.message.message_id)
    bot.send_message(id, 'Пришли файл с лабой')
    with open(f'cookies/{id}', 'w') as file:
        info = {}
        info['client_id'] = data[0]
        info['file_name'] = data[1]
        json.dump(info, file)


@bot.callback_query_handler(func=lambda call: call.data.startswith('usub'))
def view_labs(call):
    id = call.message.chat.id
    bot.delete_message(id, call.message.id)
    subject = int(call.data.split()[1])
    db_cur.execute('SELECT * FROM "%s"', (subject,))
    labs = db_cur.fetchall()
    if len(labs) > 0:
        bot.send_message(id, 'Лабы', reply_markup=btn_menu)
        for lab in labs:
            db_cur.execute('SELECT subject_output FROM subjects WHERE subject = %s', (str(subject),))
            output_subject = db_cur.fetchone()
            inl_add = types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton('Добавить', callback_data=f'add {output_subject[0]} {lab[1]} {lab[2]}'))
            inl_kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('✅Добавлено', callback_data='123'))
            bot.send_message(id, f"Предмет: {output_subject[0]}\nЛаба: №{lab[1]}\nЦена: {lab[2]}",
                             reply_markup=inl_kb if check_bucket(id, lab[1], output_subject[0]) else inl_add)
    else:
        bot.send_message(id, 'Лаб для этого предмета нет(')
        display_menu(id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('good'))
def good_order(call):
    id = call.message.chat.id
    bot.delete_message(id, call.message.message_id)
    file_name = f"{id}_{datetime.datetime.today()}".replace(' ', '').replace(':', '').replace('-', '').split('.')[
                    0] + '.json'
    db_cur.execute('INSERT INTO orders(client_id, file_name) VALUES(%s, %s)', (str(id), file_name,))
    db_con.commit()
    price = 0
    with open(f'cookies/orders/{file_name}', 'w') as file:
        shutil.copy(f'cookies/buckets/{id}.json', f'cookies/orders/{file_name}')
    with open(f'cookies/orders/{file_name}', 'r') as file:
        price = json.load(file)['total']
    bot.send_message(id,
                     'Ты можешь отправить комментарии к заказу(например: какие задания надо выполнить) используя команду /comment (какой-то коммент)')
    bot.send_message(id,
                     f'Если комментарии не нужны, сделай платеж на сумму {price}BYN через ЕРИП (Банковские, финансовые услуги - Банки, НКФО - Белинвестбанк - Пополнение счета) на номер 99oBYN-D9809D')
    bot.send_message(id, 'Жду скриншот оплаты или твой коммент')


@bot.callback_query_handler(func=lambda call: call.data.startswith('add'))
def add_in_bucket(call):
    id = call.message.chat.id
    info = call.data.split()[1:]
    inl_kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton('✅Добавлено', callback_data='123'))
    bot.edit_message_text(chat_id=id, message_id=call.message.message_id,
                          text=f'Предмет: {info[0]}\nЛаба: №{info[1]}\nЦена: {info[2]}', reply_markup=inl_kb)
    data = {}
    with open(f'cookies/buckets/{id}.json', 'r') as read_file:
        data = json.load(read_file)
    with open(f'cookies/buckets/{id}.json', 'w') as bucket:
        tmp = {
            'subject': info[0],
            'lab': f'{info[1]}',
            'price': f'{info[2]}'
        }
        data['count'] = data['count'] + 1
        data['total'] = data['total'] + float(info[2])
        data[data["count"]] = tmp
        json.dump(data, bucket)


@bot.callback_query_handler(func=lambda call: call.data.startswith('clear'))
def clear(call):
    id = call.message.chat.id
    with open(f'cookies/buckets/{id}.json', 'r') as file:
        count = json.load(file)['count']
        for i in range(0, count + 1):
            bot.delete_message(id, call.message.message_id - i)
    clear_bucket(id)
    bot.send_message(id, 'Корзина очищена')
    display_menu(id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('subject'))
def add_subject(call):
    id = call.message.chat.id
    bot.delete_message(id, call.message.id)
    bot.send_message(id, 'Введи название предмета')


@bot.callback_query_handler(func=lambda call: call.data.startswith('lab'))
def add_lab(call):
    id = call.message.chat.id
    bot.delete_message(id, call.message.id)
    inl_sub = types.InlineKeyboardMarkup()
    db_cur.execute('SELECT * FROM subjects')
    subjects = db_cur.fetchall()
    if subjects:
        for subject in subjects:
            inl_sub.add(types.InlineKeyboardButton(f"{subject[1]}", callback_data=f"sub {subject[0]}"))
        bot.send_message(id, "Выбери предмет", reply_markup=inl_sub)
    else:
        bot.send_message(id, "Еще нет предметов(")
        admin(id)


@bot.callback_query_handler(func=lambda call: call.data.startswith('sub'))
def entry_num(call):
    id = call.message.chat.id
    bot.delete_message(id, call.message.id)
    data = {
        'subject': f'{call.data.split(" ")[1]}'
    }
    with open(f'cookies/{call.message.chat.id}.json', 'w') as write_file:
        json.dump(data, write_file)
    bot.send_message(id, "Введи номер лабы и цену (#номер цена)")


@server.route(f'/{TOKEN}', methods=['POST'])
def get_message():
    json_str = request.get_data().decode('utf-8')
    update = types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return '!', 200


if __name__ == '__main__':
    bot.remove_webhook()
    bot.set_webhook(url=APP_URL)
    server.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
