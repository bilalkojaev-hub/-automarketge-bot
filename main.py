import os
import re
import sqlite3
import telebot
from flask import Flask, request
from telebot import types

TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise RuntimeError("BOT_TOKEN environment variable is missing")

bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)
DB_PATH = os.getenv("DATABASE_PATH", "automarketge.db")
user_data = {}

QUESTIONS = [
    ("brand", "🚘 Avtomobilin markasını yazın:"),
    ("model", "Modelini yazın:"),
    ("year", "İstehsal ilini yazın (məsələn 2018):"),
    ("vin", "VIN kodunu daxil edin (17 simvol):"),
    ("engine", "Mühərrik həcmini yazın (məsələn 2.0):"),
    ("fuel", "Yanacaq növünü yazın (Benzin / Dizel / Hibrid / Elektrik):"),
    ("mileage", "Yürüşü km ilə yazın:"),
    ("gearbox", "Sürətlər qutusunu yazın (Avtomat / Mexanika):"),
    ("price", "Qiyməti USD ilə yazın:"),
]


def db_connect():
    return sqlite3.connect(DB_PATH)


def init_db():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS listings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                brand TEXT NOT NULL,
                model TEXT NOT NULL,
                year TEXT NOT NULL,
                vin TEXT NOT NULL UNIQUE,
                engine TEXT NOT NULL,
                fuel TEXT NOT NULL,
                mileage TEXT NOT NULL,
                gearbox TEXT NOT NULL,
                price TEXT NOT NULL,
                photos TEXT NOT NULL,
                phone TEXT NOT NULL,
                description TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)


def send_main_menu(chat_id):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("🚗 İlan əlavə et"))
    bot.send_message(
        chat_id,
        "🚗 AutoMarketGE-yə xoş gəlmisiniz!\nAvtomobil elan platforması.",
        reply_markup=markup,
    )


def ask_next(chat_id):
    data = user_data[chat_id]
    if data["index"] < len(QUESTIONS):
        key, question = QUESTIONS[data["index"]]
        data["step"] = key
        bot.send_message(chat_id, question)
    else:
        data["step"] = "photos"
        bot.send_message(
            chat_id,
            "📸 Avtomobilin şəkillərini göndərin (1-10 şəkil).\n"
            "Şəkilləri göndərdikdən sonra /done yazın.",
        )


def start_listing(chat_id):
    user_data[chat_id] = {"index": 0, "photos": []}
    ask_next(chat_id)


def save_listing(chat_id, data):
    with db_connect() as conn:
        conn.execute("""
            INSERT INTO listings (
                user_id, brand, model, year, vin, engine, fuel,
                mileage, gearbox, price, photos, phone, description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            chat_id,
            data["brand"], data["model"], data["year"], data["vin"],
            data["engine"], data["fuel"], data["mileage"],
            data["gearbox"], data["price"],
            ",".join(data["photos"]), data["phone"], data["description"],
        ))


@bot.message_handler(commands=["start"])
def start_command(message):
    send_main_menu(message.chat.id)


@bot.message_handler(commands=["cancel"])
def cancel_command(message):
    user_data.pop(message.chat.id, None)
    bot.send_message(message.chat.id, "İlan əlavə etmə ləğv edildi.")
    send_main_menu(message.chat.id)


@bot.message_handler(commands=["done"])
def done_command(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)
    if not data or data.get("step") != "photos":
        bot.send_message(chat_id, "Hazırda şəkil mərhələsində deyilsiniz.")
        return
    if not data["photos"]:
        bot.send_message(chat_id, "Zəhmət olmasa ən azı 1 şəkil göndərin.")
        return
    data["step"] = "phone"
    bot.send_message(chat_id, "📞 Əlaqə telefon nömrənizi yazın:")


@bot.message_handler(content_types=["photo"])
def photo_handler(message):
    chat_id = message.chat.id
    data = user_data.get(chat_id)
    if not data or data.get("step") != "photos":
        return
    if len(data["photos"]) >= 10:
        bot.send_message(chat_id, "Maksimum 10 şəkil qəbul edilir. Bitirmək üçün /done yazın.")
        return
    data["photos"].append(message.photo[-1].file_id)
    bot.send_message(chat_id, f"✅ Şəkil qəbul edildi: {len(data['photos'])}/10")


@bot.message_handler(content_types=["text"])
def text_handler(message):
    chat_id = message.chat.id
    text = message.text.strip()

    if text == "🚗 İlan əlavə et":
        start_listing(chat_id)
        return

    if text == "❌ Ləğv et":
        user_data.pop(chat_id, None)
        bot.send_message(chat_id, "İlan ləğv edildi.")
        send_main_menu(chat_id)
        return

    data = user_data.get(chat_id)
    if not data:
        bot.send_message(chat_id, "Başlamaq üçün /start yazın.")
        return

    step = data.get("step")

    if step == "photos":
        bot.send_message(chat_id, "Şəkilləri göndərin. Bitirdikdə /done yazın.")
        return

    if step == "phone":
        if len(text) < 5:
            bot.send_message(chat_id, "Düzgün telefon nömrəsi daxil edin.")
            return
        data["phone"] = text
        data["step"] = "description"
        bot.send_message(chat_id, "📝 Avtomobil haqqında əlavə məlumat yazın:")
        return

    if step == "description":
        data["description"] = text
        data["step"] = "confirm"
        summary = (
            "🚗 ELAN MƏLUMATLARI\n\n"
            f"Marka: {data['brand']}\n"
            f"Model: {data['model']}\n"
            f"İl: {data['year']}\n"
            f"VIN: {data['vin']}\n"
            f"Mühərrik: {data['engine']}\n"
            f"Yanacaq: {data['fuel']}\n"
            f"Yürüş: {data['mileage']} km\n"
            f"Sürətlər qutusu: {data['gearbox']}\n"
            f"Qiymət: ${data['price']}\n"
            f"Şəkil sayı: {len(data['photos'])}\n"
            f"Telefon: {data['phone']}\n"
            f"Açıqlama: {data['description']}\n\n"
            "Elanı təsdiqləyirsiniz?"
        )
        markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add("✅ Təsdiqlə", "❌ Ləğv et")
        bot.send_message(chat_id, summary, reply_markup=markup)
        return

    if step == "confirm":
        if text != "✅ Təsdiqlə":
            bot.send_message(chat_id, "Zəhmət olmasa ✅ Təsdiqlə və ya ❌ Ləğv et seçin.")
            return
        try:
            save_listing(chat_id, data)
            user_data.pop(chat_id, None)
            bot.send_message(chat_id, "🎉 Elanınız uğurla qeydə alındı!")
            send_main_menu(chat_id)
        except sqlite3.IntegrityError:
            user_data.pop(chat_id, None)
            bot.send_message(chat_id, "Bu VIN kodu ilə artıq elan mövcuddur.")
            send_main_menu(chat_id)
        except Exception as exc:
            app.logger.exception("Could not save listing: %s", exc)
            bot.send_message(chat_id, "Xəta baş verdi. Bir az sonra yenidən cəhd edin.")
        return

    if step == "year":
        if not text.isdigit() or not 1900 <= int(text) <= 2026:
            bot.send_message(chat_id, "1900-2026 arası düzgün istehsal ili daxil edin.")
            return

    if step == "vin":
        text = text.upper()
        if not re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", text):
            bot.send_message(chat_id, "VIN 17 simvol olmalıdır. I, O və Q hərfləri qəbul edilmir.")
            return
        with db_connect() as conn:
            exists = conn.execute("SELECT 1 FROM listings WHERE vin = ?", (text,)).fetchone()
        if exists:
            bot.send_message(chat_id, "Bu VIN kodu ilə artıq elan mövcuddur.")
            return

    if step == "mileage":
        if not text.isdigit():
            bot.send_message(chat_id, "Yürüşü yalnız rəqəmlə daxil edin.")
            return

    if step == "price":
        try:
            if float(text.replace(",", ".")) <= 0:
                raise ValueError
        except ValueError:
            bot.send_message(chat_id, "Düzgün, sıfırdan böyük qiymət daxil edin.")
            return

    if step not in [item[0] for item in QUESTIONS]:
        bot.send_message(chat_id, "Davam etmək üçün /start yazın.")
        return

    data[step] = text
    data["index"] += 1
    ask_next(chat_id)


@app.route("/")
def home():
    return "AutoMarketGE Bot is running!", 200


@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = telebot.types.Update.de_json(request.get_json(force=True))
        bot.process_new_updates([update])
        return "OK", 200
    except Exception:
        app.logger.exception("Webhook processing failed")
        return "ERROR", 500


@app.route("/set_webhook")
def set_webhook():
    external_url = os.getenv("RENDER_EXTERNAL_URL")
    if not external_url:
        return "RENDER_EXTERNAL_URL is missing", 500
    bot.remove_webhook()
    bot.set_webhook(url=external_url.rstrip("/") + "/webhook")
    return "Webhook aktivdir!", 200


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
