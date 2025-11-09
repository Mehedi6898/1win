import asyncio
import random
import json
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask, request
import threading
import os

# === CONFIG ===
BOT_TOKEN = "8239639639:AAHyf5kSuSV7ZwiKTd1x3rLeMLOLXIKUzrc"  # replace with your actual bot token
MIN_DEPOSIT = 50.0
AFFILIATE_BASE = "https://1wrpdq.com/?open=register&p=8ay6"
DATA_FILE = "users.json"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
app = Flask(__name__)

# === LOAD DATA ===
if os.path.exists(DATA_FILE):
    try:
        with open(DATA_FILE, "r") as f:
            user_data = json.load(f)
    except Exception:
        user_data = {}
else:
    user_data = {}

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(user_data, f, indent=2)

# === TELEGRAM COMMANDS ===
@dp.message_handler(commands=["start"])
async def start_cmd(message: types.Message):
    uid = str(message.from_user.id)
    user_data.setdefault(uid, {"deposit": 0.0, "registered": False, "qualified": False, "running": False})
    save_data()

    register_button = InlineKeyboardButton("🔗 Register Here", url=f"{AFFILIATE_BASE}&subid={uid}")
    check_registration_button = InlineKeyboardButton("✅ Check Registration", callback_data="check_registration")
    markup = InlineKeyboardMarkup().add(register_button).add(check_registration_button)

    text = (
        f"Hey {message.from_user.first_name}! 👋 Welcome to the *King Predictor* 🎁\n\n"
        "Follow the steps below to start receiving predictions:\n"
        "1️⃣ Register using your personal link below.\n"
        "2️⃣ Deposit at least **$50** on your account.\n"
        "3️⃣ Check your progress step-by-step.\n\n"
        "_Tap below to begin:_"
    )

    await message.answer(text, parse_mode="Markdown", reply_markup=markup)

# === CHECK REGISTRATION ===
@dp.callback_query_handler(lambda c: c.data == "check_registration")
async def check_registration(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    user = user_data.get(uid, {"registered": False})

    if not user.get("registered"):
        await call.message.answer("❌ You haven’t registered yet.\n\nRegister with your personal link first!", parse_mode="Markdown")
        return

    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("💵 Check Deposit", callback_data="check_deposit")
    )

    await call.message.answer(
        "✅ Registration confirmed!\n\n"
        "Now deposit **$50 or more** to unlock predictions.\n"
        "Once done, tap below to verify your deposit 👇",
        parse_mode="Markdown",
        reply_markup=markup
    )

# === CHECK DEPOSIT ===
@dp.callback_query_handler(lambda c: c.data == "check_deposit")
async def check_deposit(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    user = user_data.get(uid, {"deposit": 0.0})
    dep = float(user.get("deposit", 0.0))

    if dep <= 0:
        await call.message.answer("😅 No deposit detected yet. Try again later.")
        return

    if dep < MIN_DEPOSIT:
        remain = MIN_DEPOSIT - dep
        await call.message.answer(f"You’ve deposited ${dep:.2f}. Deposit ${remain:.2f} more to unlock 🔓")
        return

    if not user.get("qualified"):
        user["qualified"] = True
        save_data()

    markup = InlineKeyboardMarkup().add(
        InlineKeyboardButton("▶️ Start Predictor", callback_data="start_numbers"),
        InlineKeyboardButton("⏹ Stop", callback_data="stop_numbers")
    )

    await call.message.answer("🔥 Deposit confirmed! You’re now qualified.", reply_markup=markup)

# === PREDICTOR LOGIC ===
@dp.callback_query_handler(lambda c: c.data == "start_numbers")
async def start_numbers(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    user = user_data.get(uid, {})
    if not user.get("qualified"):
        await call.message.answer("Deposit at least $50 first 💰")
        return
    if user.get("running"):
        await call.message.answer("Already running ⏳")
        return

    user["running"] = True
    save_data()

    msg = await call.message.answer("🎯 Number: Starting...")
    while user_data.get(uid, {}).get("running"):
        # 70% chance for 1–30, 30% for 30.01–300
        if random.random() < 0.7:
            num = round(random.uniform(1, 30), 2)
        else:
            num = round(random.uniform(30.01, 300), 2)

        try:
            await msg.edit_text(f"🎯 Number: {num}")
        except Exception:
            pass

        # dynamic delay
        if num < 10:
            delay = 10
        elif num < 30:
            delay = random.randint(15, 25)
        elif num < 100:
            delay = random.randint(25, 45)
        else:
            delay = random.randint(45, 60)

        await asyncio.sleep(delay)

    await call.message.answer("Stopped ⏹️")

@dp.callback_query_handler(lambda c: c.data == "stop_numbers")
async def stop_numbers(call: types.CallbackQuery):
    uid = str(call.from_user.id)
    if uid in user_data:
        user_data[uid]["running"] = False
        save_data()
    await call.message.answer("✅ Predictor stopped.")

# === POSTBACK HANDLER ===
@app.route("/postback", methods=["GET", "POST"])
def postback():
    subid = request.args.get("subid")
    event = request.args.get("event", "")
    amount_raw = request.args.get("amount", "0")

    try:
        amount = float(amount_raw)
    except:
        amount = 0.0

    if not subid:
        return "Missing subid", 400

    uid = str(subid)
    user_data.setdefault(uid, {"deposit": 0.0, "registered": False, "qualified": False, "running": False})

    if event.lower() == "registration":
        user_data[uid]["registered"] = True
        save_data()
        print(f"[POSTBACK] User {uid} registered ✅")
        return "OK", 200

    if event.lower() == "deposit":
        user_data[uid]["deposit"] = float(user_data[uid].get("deposit", 0.0)) + amount
        save_data()
        print(f"[POSTBACK] User {uid} deposited ${amount:.2f} 💰")
        return "OK", 200

    return "Invalid event", 400

# === SERVER THREADS ===
def run_flask():
    port = int(os.environ.get("PORT", "10000"))
    app.run(host="0.0.0.0", port=port)

def run_telegram():
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    run_telegram()
