
import os
import telebot

TOKEN = os.getenv("BOT_TOKEN")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    bot.reply_to(
        message,
        "🚗 AutoMarketGE-yə xoş gəlmisiniz!\n\n"
        "Avtomobil elanları üçün botumuz aktivdir."
    )

@bot.message_handler(func=lambda message: True)
def echo(message):
    bot.reply_to(message, "Mesajınız qəbul edildi. 🚘")

bot.infinity_polling()
