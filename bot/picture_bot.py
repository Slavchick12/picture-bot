import ast
import csv
import os

import redis
import requests
import telebot
from utils.consts import *
from dotenv import load_dotenv
from telebot import types

load_dotenv()

BOT_API_TOKEN = '6237244785:AAFmUZcfW_zCRdVPu1GkSJO-cQe9JfD9gog'  # There is no environ for simplified test

r = redis.Redis(host=os.getenv('HOST'), port=os.getenv('PORT'), db=os.getenv('DB'))

bot = telebot.TeleBot(BOT_API_TOKEN)

main_keyboard = types.InlineKeyboardMarkup(row_width=1)
invalid_link_keyboard = types.InlineKeyboardMarkup(row_width=1)
picture_keyboard = types.InlineKeyboardMarkup(row_width=1)
confirm_keyboard = types.InlineKeyboardMarkup(row_width=2)

add_picture_button = types.InlineKeyboardButton(ADD_PICTURES, callback_data=ADD_PICTURE_BUTTON)
picture_list_button = types.InlineKeyboardButton(PICTURE_LIST, callback_data=PICTURE_LIST_BUTTON)
picture_table_button = types.InlineKeyboardButton(GET_PICTURE_TABLE, callback_data=PICTURE_TABLE_BUTTON)
to_main_button = types.InlineKeyboardButton(TO_MAIN, callback_data=TO_MAIN_BUTTON)
delete_button = types.InlineKeyboardButton(DELETE, callback_data=DELETE_BUTTON)
back_button = types.InlineKeyboardButton(BACK, callback_data=BACK_BUTTON)
yes_button = types.InlineKeyboardButton(YES, callback_data=YES_BUTTON)
no_button = types.InlineKeyboardButton(NO, callback_data=NO_BUTTON)

main_keyboard.add(add_picture_button)
main_keyboard.add(picture_list_button)
invalid_link_keyboard.add(to_main_button)
picture_keyboard.add(delete_button)
picture_keyboard.add(back_button)
confirm_keyboard.add(yes_button)
confirm_keyboard.add(no_button)


@bot.message_handler(commands=['start'])
def send_welcome(message):
    """
    Welcome handler.
    """
    chat_id = message.chat.id
    bot.send_message(chat_id, WELCOME_MESSAGE, disable_web_page_preview=True)
    bot.register_next_step_handler_by_chat_id(chat_id, first_mesages)


@bot.message_handler(content_types=['text'])
def get_picture_link(message):
    """
    Messages handler.
    """
    chat_id = message.chat.id
    pictures = check_link(message.text)

    if not pictures:
        bot.send_message(chat_id, RETRY_LINK, reply_markup=invalid_link_keyboard)
    else:
        add_pictures(pictures, chat_id)
        bot.send_message(chat_id, SAVES_SUCCESSFULLY)
        bot.send_message(chat_id, MAIN_MENU, reply_markup=main_keyboard)


@bot.message_handler(content_types=['text'])
def first_mesages(message):
    """
    Handler of the next message from the user after '/start'.
    """
    chat_id = message.chat.id
    pictures = check_link(message.text)

    if not pictures:
        bot.send_message(chat_id, INVALID_LINK)
    else:
        add_pictures(pictures, chat_id)
        bot.send_message(chat_id, SAVES_SUCCESSFULLY)

    bot.send_message(chat_id, MAIN_MENU, reply_markup=main_keyboard)

    if len(main_keyboard.keyboard) < 3:
        main_keyboard.add(picture_table_button)


@bot.callback_query_handler(func=lambda call: True)
def callback_inline(call):
    """
    Buttons handler.
    """
    message, data = call.message, call.data
    chat_id, message_id = message.chat.id, message.id

    if data == ADD_PICTURE_BUTTON:
        bot.edit_message_text(text=GIVE_LINK, chat_id=chat_id, message_id=message_id, disable_web_page_preview=True)

    elif data == PICTURE_LIST_BUTTON:
        keyboard = get_picture_keyboard(chat_id)
        bot.delete_message(chat_id=chat_id, message_id=message_id)

        with open(EMPTY_PICTURE, 'rb') as picture:
            bot.send_photo(chat_id=chat_id, photo=picture, caption=PICTURE_LIST, reply_markup=keyboard)

    elif data == TO_MAIN_BUTTON:
        try:
            bot.edit_message_text(text=MAIN_MENU, chat_id=chat_id, message_id=message_id, reply_markup=main_keyboard)
        except Exception:
            bot.delete_message(chat_id=chat_id, message_id=message_id)
            bot.send_message(chat_id=chat_id, text=MAIN_MENU, reply_markup=main_keyboard)

    elif data == DELETE_BUTTON:
        author_id_str = get_author_id_str(message.caption)

        bot.edit_message_caption(
            caption=f'Вы уверены, что хотите удалить эту фотографию? {author_id_str}', chat_id=chat_id,
            message_id=message_id, reply_markup=confirm_keyboard
        )

    elif data == YES_BUTTON:
        delete_picture(chat_id, message.caption)
        bot.delete_message(chat_id=chat_id, message_id=message_id)
        bot.send_message(chat_id=chat_id, text=PICTURE_DELETED)
        keyboard = get_picture_keyboard(chat_id)

        with open(EMPTY_PICTURE, 'rb') as picture:
            bot.send_photo(chat_id=chat_id, photo=picture, caption=PICTURE_LIST, reply_markup=keyboard)

    elif data == NO_BUTTON or data == BACK_BUTTON:
        redirect_to_main_pictures(chat_id, message_id)

    elif data == PICTURE_TABLE_BUTTON:
        create_pictures_csv(chat_id)

        with open(TABLE_PICTURE, 'rb') as document:
            bot.send_document(chat_id=chat_id, document=document)

    else:
        url, text = get_picture_info(chat_id, data)
        picture = telebot.types.InputMediaPhoto(url)

        bot.edit_message_media(media=picture, chat_id=chat_id, message_id=message_id)
        bot.edit_message_caption(
            caption=text, chat_id=chat_id, message_id=message_id, reply_markup=picture_keyboard
        )


def add_pictures(pictures, chat_id):
    """
    Add pictures to Redis.
    """
    user_pictures = r.get(chat_id)
    user_all_pictures = {}

    if user_pictures:
        current_pictures = ast.literal_eval(user_pictures.decode())
        user_all_pictures = {**user_all_pictures, **current_pictures}

    for picture in pictures:
        user_all_pictures[picture['id']] = picture

    r.set(chat_id, f'{user_all_pictures}')


def get_picture_keyboard(chat_id):
    """
    Keyboard generator with pictures.
    """
    user_pictures = r.get(chat_id)
    pictures_keyboard = types.InlineKeyboardMarkup(row_width=1)

    if user_pictures:
        pictures_dict = ast.literal_eval(user_pictures.decode())

        for id_ in pictures_dict:
            author_id_format = f"{pictures_dict[id_]['author']} ({id_})"
            pictures_keyboard.add(types.InlineKeyboardButton(author_id_format, callback_data=author_id_format))

    pictures_keyboard.add(to_main_button)

    return pictures_keyboard


def get_picture_info(chat_id, data):
    """
    Get picture info text and picture url.
    """
    picture_id = data[data.find('(') + 1: data.find(')')]
    user_pictures = r.get(chat_id)
    pictures_dict = ast.literal_eval(user_pictures.decode())

    pictire_info = pictures_dict[picture_id]
    url = pictire_info['url']
    text = f"Author: {pictire_info['author']}\nID: {picture_id}\nSize: {pictire_info['width']}x{pictire_info['height']}\
        \nURL: {url}\nDownload_URL: {pictire_info['download_url']}\n"

    return url, text


def delete_picture(chat_id, text):
    """
    Deleting a user's image from the database.
    """
    user_pictures = r.get(chat_id)
    pictures_dict = ast.literal_eval(user_pictures.decode())
    delete_picture_id = text[text.find('(') + 1: text.find(')')]

    del pictures_dict[delete_picture_id]
    r.set(chat_id, f'{pictures_dict}')


def get_author_id_str(string):
    """
    String reformat.
    """
    author = string[string.find(' ') + 1: string.find('\nID')]
    id_ = string[string.find('ID: ') + 4: string.find('\nSize')]
    author_id_str = f'{author} ({id_})'
    return author_id_str


def redirect_to_main_pictures(chat_id, message_id):
    """
    Redirect to main pictures.
    """
    keyboard = get_picture_keyboard(chat_id)

    with open(EMPTY_PICTURE, 'rb') as picture:
        media = telebot.types.InputMediaPhoto(picture)
        bot.edit_message_media(media=media, chat_id=chat_id, message_id=message_id)
        bot.edit_message_caption(caption=PICTURE_LIST, chat_id=chat_id, message_id=message_id, reply_markup=keyboard)


def check_link(link):
    """
    Link validator.
    """
    try:
        response = requests.get(link)
    except Exception:
        return False

    if response.status_code == 200:
        return response.json()

    return False


def create_pictures_csv(chat_id):
    """
    Generating a csv-file with user images.
    """
    user_pictures = r.get(chat_id)
    pictures_dict = ast.literal_eval(user_pictures.decode())
    lines = [['id', 'author', 'width', 'height', 'url', 'download_url']]

    for id_ in pictures_dict:
        lines.append([])
        for _, v in pictures_dict[id_].items():
            lines[-1].append(v)

    with open(TABLE_PICTURE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(lines)


def main():
    bot.infinity_polling()


if __name__ == '__main__':
    main()
