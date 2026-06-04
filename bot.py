import logging
import os
import json
import asyncio
from datetime import datetime
import requests as req
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler
)

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
ADMIN_CHAT_ID  = os.environ.get("ADMIN_CHAT_ID", "YOUR_TELEGRAM_ID")
CHANNEL_LINK   = "https://t.me/shaylionlineshop"
BALE_LINK      = "http://ble.ir/shaylionlineshop"
PHONE          = "09040710470"
INSTAGRAM      = "https://www.instagram.com/shaylionlineshop"
DB_FILE        = "shayli_db.json"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

(ORDER_COUNTRY, ORDER_PRODUCT, ORDER_NAME, ORDER_PHONE, ORDER_ADDRESS, ORDER_POSTAL, ORDER_RECEIPT) = range(7)
(PROFILE_NAME, PROFILE_BIRTHDAY) = range(10, 12)
(ADMIN_BROADCAST, ADMIN_TRACKING_ID, ADMIN_TRACKING_CODE, ADMIN_DISCOUNT_ID, ADMIN_DISCOUNT_MSG) = range(20, 25)

def load_db():
    if os.path.exists(DB_FILE):
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"users": {}, "orders": [], "order_counter": 1000}

def save_db(db):
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

def get_user(db, chat_id):
    return db["users"].get(str(chat_id), {})

def save_user(db, chat_id, data):
    db["users"][str(chat_id)] = data
    save_db(db)

SYSTEM_PROMPT = """تو دستیار هوشمند آنلاین‌شاپ شایلی هستی. اسمت «شایلی» هست.

اطلاعات فروشگاه:
- محصولات: لوازم آرایشی، لوازم خانه، ورزشی، مردانه، زنانه، بچه‌گانه، کیف، کفش
- کشورها: امارات (عمده)، ترکیه، کانادا، آمریکا
- زمان تحویل ترکیه: ۲ تا ۴ هفته (شرایط فعلی)
- زمان تحویل امارات: ۴ تا ۷ هفته (شرایط فعلی)
- باربری امارات: لباس/اکسسوری هر ۱۰۰گرم=۹۹,۰۰۰ت | کفش جفتی=۶۵۰,۰۰۰ت | کیف دانه‌ای=۶۰۰,۰۰۰ت
- باربری ترکیه: هر ۱۰۰گرم=۵۸,۰۰۰ت (هوایی)
- پرداخت: کارت به کارت - شماره کارت از ادمین
- تعویض نداریم. آسیب دیده؟ تا ۴۸ساعت عکس بفرست
- موجودی: «موجود در ایران» نوشته=موجود، نوشته نشده=سفارشی
- کانال: t.me/shaylionlineshop
- بله: ble.ir/shaylionlineshop
- تماس اضطراری: 09040710470
- قیمت محصول: از ادمین بپرس

همیشه صمیمی و دوستانه باش. برای ثبت سفارش بگو دکمه ثبت سفارش رو بزنن. پیام کوتاه و مفید باشه."""

def ask_ai(user_message, history):
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
        contents = []
        for h in history[-10:]:
            contents.append({"role": h["role"], "parts": [{"text": h["text"]}]})
        contents.append({"role": "user", "parts": [{"text": f"{SYSTEM_PROMPT}\n\nپیام مشتری: {user_message}"}]})
        response = req.post(url, json={"contents": contents}, timeout=15)
        data = response.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        logger.error(f"AI error: {e}")
        return "عزیزم یه مشکل پیش اومد 😅 دوباره امتحان کن یا مستقیم پیام بده."

def main_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("🛍️ ثبت سفارش"), KeyboardButton("🔍 جستجو محصول")],
        [KeyboardButton("📦 پیگیری سفارش"), KeyboardButton("❓ سوالات متداول")],
        [KeyboardButton("📞 ارتباط با ما"), KeyboardButton("👤 پروفایل من")],
    ], resize_keyboard=True)

def admin_keyboard():
    return ReplyKeyboardMarkup([
        [KeyboardButton("📢 پیام همگانی"), KeyboardButton("📦 ثبت کد پیگیری")],
        [KeyboardButton("🎁 ارسال تخفیف"), KeyboardButton("📊 آمار ربات")],
        [KeyboardButton("🔙 خروج از پنل")],
    ], resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id
    db = load_db()
    if not get_user(db, chat_id):
        save_user(db, chat_id, {
            "chat_id": chat_id,
            "first_name": update.effective_user.first_name or "",
            "username": update.effective_user.username or "",
            "joined": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "full_name": "", "birthday": "", "orders": []
        })
    context.user_data["history"] = []
    name = update.effective_user.first_name or "عزیزم"
    await update.message.reply_text(
        f"سلام {name} جان! 👋\n\nبه آنلاین‌شاپ شایلی خوش اومدی 🌟\nبهترین محصولات از امارات، ترکیه، کانادا و آمریکا 🛒\n\nچطور می‌تونم کمکت کنم؟ 😊",
        reply_markup=main_keyboard()
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return
    db = load_db()
    await update.message.reply_text(
        f"👑 *پنل مدیریت شایلی*\n\n👥 کاربران: {len(db['users'])}\n🛍️ سفارشات: {len(db['orders'])}",
        parse_mode="Markdown", reply_markup=admin_keyboard()
    )

async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👤 اسم و فامیلت رو بنویس:", reply_markup=ReplyKeyboardRemove())
    return PROFILE_NAME

async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["pname"] = update.message.text
    await update.message.reply_text("🎂 تاریخ تولدت رو بنویس:\n_(مثلاً ۱۵/۶)_", parse_mode="Markdown")
    return PROFILE_BIRTHDAY

async def profile_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    uid = update.effective_user.id
    user = get_user(db, uid)
    user["full_name"] = context.user_data["pname"]
    user["birthday"] = update.message.text
    save_user(db, uid, user)
    await update.message.reply_text(
        f"✅ پروفایل ذخیره شد!\n📛 {user['full_name']}\n🎂 {user['birthday']}\n\nروز تولدت کد تخفیف ویژه میفرستم 🎉",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"] = {}
    await update.message.reply_text(
        "🛍️ *ثبت سفارش شایلی*\n\nاز کدوم کشور؟",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardMarkup([
            [KeyboardButton("🇦🇪 امارات"), KeyboardButton("🇹🇷 ترکیه")],
            [KeyboardButton("🇨🇦 کانادا"), KeyboardButton("🇺🇸 آمریکا")],
        ], resize_keyboard=True, one_time_keyboard=True)
    )
    return ORDER_COUNTRY

async def order_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["country"] = update.message.text
    await update.message.reply_text("محصولی که می‌خوای رو توضیح بده:\n_(لینک، عکس، اسم برند، رنگ، سایز)_", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return ORDER_PRODUCT

async def order_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["order"]["product"] = f"[عکس - {update.message.photo[-1].file_id}]" + (f" | {update.message.caption}" if update.message.caption else "")
    else:
        context.user_data["order"]["product"] = update.message.text
    await update.message.reply_text("نام و نام خانوادگی کاملت:")
    return ORDER_NAME

async def order_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["name"] = update.message.text
    await update.message.reply_text("شماره موبایل:")
    return ORDER_PHONE

async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        await update.message.reply_text("⚠️ شماره باید با ۰۹ شروع و ۱۱ رقم باشه:")
        return ORDER_PHONE
    context.user_data["order"]["phone"] = phone
    await update.message.reply_text("آدرس کامل:\n_(استان، شهر، خیابان، پلاک، واحد)_", parse_mode="Markdown")
    return ORDER_ADDRESS

async def order_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["address"] = update.message.text
    await update.message.reply_text("کد پستی ۱۰ رقمی:")
    return ORDER_POSTAL

async def order_postal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    postal = update.message.text.strip()
    if not (len(postal) == 10 and postal.isdigit()):
        await update.message.reply_text("⚠️ کد پستی باید ۱۰ رقم باشه:")
        return ORDER_POSTAL
    context.user_data["order"]["postal"] = postal
    o = context.user_data["order"]
    await update.message.reply_text(
        f"🧾 *خلاصه سفارش:*\n\n🌍 {o['country']}\n📦 {o['product']}\n👤 {o['name']}\n📱 {o['phone']}\n📍 {o['address']}\n📮 {o['postal']}\n\n💳 برای شماره کارت به ادمین پیام بده.\nبعد از پرداخت، فیش رو اینجا بفرست 👇",
        parse_mode="Markdown"
    )
    return ORDER_RECEIPT

async def order_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        receipt = f"[عکس فیش - {update.message.photo[-1].file_id}]"
    elif update.message.document:
        receipt = f"[فایل - {update.message.document.file_id}]"
    elif update.message.text:
        receipt = update.message.text
    else:
        await update.message.reply_text("⚠️ عکس یا متن فیش رو بفرست.")
        return ORDER_RECEIPT

    db = load_db()
    order_id = f"SH{db['order_counter']}"
    db["order_counter"] += 1
    chat_id = update.effective_user.id
    o = context.user_data["order"]
    o.update({"receipt": receipt, "order_id": order_id, "date": datetime.now().strftime("%Y-%m-%d %H:%M"), "status": "در انتظار بررسی", "chat_id": chat_id})
    db["orders"].append(o)
    user = get_user(db, chat_id)
    if "orders" not in user: user["orders"] = []
    user["orders"].append(order_id)
    user["last_order"] = datetime.now().isoformat()
    save_user(db, chat_id, user)
    save_db(db)

    tg = update.effective_user
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, parse_mode="Markdown",
            text=f"🔔 *سفارش جدید!*\n\n🆔 `{order_id}`\n👤 {tg.first_name} (@{tg.username or '-'})\n🆔 Chat: `{chat_id}`\n\n🌍 {o['country']}\n📦 {o['product']}\n👤 {o['name']}\n📱 {o['phone']}\n📍 {o['address']}\n📮 {o['postal']}\n🧾 {o['receipt']}")
    except Exception as e:
        logger.error(f"Admin notify: {e}")

    await update.message.reply_text(
        f"✅ *سفارش ثبت شد!*\n\n🎉 کد سفارش: `{order_id}`\nاین کد رو نگه‌دار 📌\n\n━━━━━━━━━━━━━━\n📣 برای دسترسی به اینترنت در کانال بله عضو شو:\n{BALE_LINK}",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def tracking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user = get_user(db, update.effective_user.id)
    if not user.get("orders"):
        await update.message.reply_text("📦 سفارشی ثبت نشده.\nکد سفارشت رو بنویس تا چک کنم.", reply_markup=main_keyboard())
        return
    msg = "📦 *سفارش‌های شما:*\n\n"
    for oid in user["orders"][-5:]:
        for o in db["orders"]:
            if o.get("order_id") == oid:
                msg += f"🔖 `{oid}` | {o.get('date','-')} | {o.get('status','در انتظار')}\n"
                if o.get("tracking_code"):
                    msg += f"🚚 کد پیگیری: `{o['tracking_code']}`\n"
                msg += "─────\n"
    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID): return
    await update.message.reply_text("📢 متن پیام همگانی رو بنویس:", reply_markup=ReplyKeyboardRemove())
    return ADMIN_BROADCAST

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    msg = update.message.text
    sent = failed = 0
    for uid in db["users"]:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 *پیام از شایلی:*\n\n{msg}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except: failed += 1
    await update.message.reply_text(f"✅ فرستاده شد!\n✔️ موفق: {sent}\n❌ ناموفق: {failed}", reply_markup=admin_keyboard())
    return ConversationHandler.END

async def tracking_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID): return
    await update.message.reply_text("کد سفارش رو بنویس (مثلاً SH1001):", reply_markup=ReplyKeyboardRemove())
    return ADMIN_TRACKING_ID

async def tracking_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["t_oid"] = update.message.text.strip()
    await update.message.reply_text("کد تیپاکس / ماهکس / پست:")
    return ADMIN_TRACKING_CODE

async def tracking_admin_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    oid = context.user_data["t_oid"]
    code = update.message.text.strip()
    found = False
    for o in db["orders"]:
        if o.get("order_id") == oid:
            o["tracking_code"] = code
            o["status"] = "ارسال شده 🚚"
            found = True
            try:
                await context.bot.send_message(chat_id=o["chat_id"], parse_mode="Markdown",
                    text=f"🚚 *سفارش شما ارسال شد!*\n\n🔖 `{oid}`\n📮 کد پیگیری: `{code}`\n\nاز سایت تیپاکس یا ماهکس پیگیری کنید 😊")
            except: pass
            break
    save_db(db)
    await update.message.reply_text("✅ ثبت شد و به مشتری اطلاع داده شد!" if found else f"❌ سفارش {oid} پیدا نشد.", reply_markup=admin_keyboard())
    return ConversationHandler.END

async def discount_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID): return
    db = load_db()
    lst = "\n".join([f"`{uid}` - {u.get('full_name') or u.get('first_name','؟')}" for uid, u in list(db["users"].items())[:15]])
    await update.message.reply_text(f"🎁 Chat ID مشتری رو بنویس:\n\n{lst}", parse_mode="Markdown", reply_markup=ReplyKeyboardRemove())
    return ADMIN_DISCOUNT_ID

async def discount_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["d_cid"] = update.message.text.strip()
    await update.message.reply_text("متن پیام تخفیف:")
    return ADMIN_DISCOUNT_MSG

async def discount_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_message(chat_id=int(context.user_data["d_cid"]),
            text=f"🎁 *پیام ویژه از شایلی:*\n\n{update.message.text}\n\nبرای استفاده پیام بده 😊", parse_mode="Markdown")
        await update.message.reply_text("✅ فرستاده شد!", reply_markup=admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}", reply_markup=admin_keyboard())
    return ConversationHandler.END

async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID): return
    db = load_db()
    pending = sum(1 for o in db["orders"] if o.get("status") == "در انتظار بررسی")
    sent = sum(1 for o in db["orders"] if "ارسال" in o.get("status",""))
    await update.message.reply_text(
        f"📊 *آمار شایلی*\n\n👥 کاربران: {len(db['users'])}\n🛍️ سفارشات: {len(db['orders'])}\n⏳ در انتظار: {pending}\n🚚 ارسال شده: {sent}",
        parse_mode="Markdown", reply_markup=admin_keyboard()
    )

async def faq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "❓ *سوالات متداول شایلی*\n\n"
        "⏰ *زمان تحویل:*\n• ترکیه: ۲ تا ۴ هفته\n• امارات: ۴ تا ۷ هفته\n\n"
        "💰 *باربری امارات:*\n• لباس/اکسسوری: هر ۱۰۰گرم=۹۹,۰۰۰ت\n• کفش: جفتی=۶۵۰,۰۰۰ت\n• کیف: دانه‌ای=۶۰۰,۰۰۰ت\n\n"
        "💰 *باربری ترکیه:*\n• هر ۱۰۰گرم=۵۸,۰۰۰ت\n\n"
        "💳 *پرداخت:* کارت به کارت\n\n"
        "❌ *تعویض نداریم*\nآسیب دیده؟ تا ۴۸ساعت عکس بفرست\n\n"
        "📦 *موجودی:* «موجود در ایران»=موجود، غیر اینصورت=سفارشی",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📞 *ارتباط با شایلی*\n\n📱 اضطراری: `{PHONE}`\n📣 تلگرام: {CHANNEL_LINK}\n📸 اینستاگرام: {INSTAGRAM}\n🔵 بله: {BALE_LINK}\n\n⏰ شنبه تا پنجشنبه ۱۰ تا ۲۲",
        parse_mode="Markdown", reply_markup=main_keyboard()
    )

async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"🔍 کانال ما رو چک کن 👇\n{CHANNEL_LINK}\n\nلینک یا عکس محصول رو بفرست، ثبت میکنم 🛍️\n\n💡 «موجود در ایران»=موجود | بدون نوشته=سفارشی",
        reply_markup=main_keyboard()
    )

async def conv_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لغو شد 😊", reply_markup=main_keyboard())
    return ConversationHandler.END

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text if update.message.text else ""
    if text == "❓ سوالات متداول": return await faq_handler(update, context)
    if text == "📞 ارتباط با ما": return await contact_handler(update, context)
    if text == "📦 پیگیری سفارش": return await tracking_handler(update, context)
    if text == "🔍 جستجو محصول": return await search_handler(update, context)
    if text == "📊 آمار ربات": return await stats_handler(update, context)
    if text == "🔙 خروج از پنل":
        await update.message.reply_text("برگشتیم 😊", reply_markup=main_keyboard())
        return

    db = load_db()
    uid = update.effective_user.id
    user = get_user(db, uid)
    if user:
        user["last_active"] = datetime.now().isoformat()
        save_user(db, uid, user)

    if "history" not in context.user_data:
        context.user_data["history"] = []

    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    reply = ask_ai(text, context.user_data["history"])
    context.user_data["history"].append({"role": "user", "text": text})
    context.user_data["history"].append({"role": "model", "text": reply})
    if len(context.user_data["history"]) > 20:
        context.user_data["history"] = context.user_data["history"][-20:]
    await update.message.reply_text(reply, reply_markup=main_keyboard())

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    order_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🛍️ ثبت سفارش$"), order_start)],
        states={
            ORDER_COUNTRY:  [MessageHandler(filters.TEXT & ~filters.COMMAND, order_country)],
            ORDER_PRODUCT:  [MessageHandler((filters.TEXT | filters.PHOTO) & ~filters.COMMAND, order_product)],
            ORDER_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, order_name)],
            ORDER_PHONE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, order_phone)],
            ORDER_ADDRESS:  [MessageHandler(filters.TEXT & ~filters.COMMAND, order_address)],
            ORDER_POSTAL:   [MessageHandler(filters.TEXT & ~filters.COMMAND, order_postal)],
            ORDER_RECEIPT:  [MessageHandler(filters.ALL & ~filters.COMMAND, order_receipt)],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
    )

    profile_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👤 پروفایل من$"), profile_start)],
        states={
            PROFILE_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name)],
            PROFILE_BIRTHDAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_birthday)],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
    )

    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 پیام همگانی$"), broadcast_start)],
        states={ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=[CommandHandler("cancel", conv_cancel)],
    )

    tracking_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📦 ثبت کد پیگیری$"), tracking_admin_start)],
        states={
            ADMIN_TRACKING_ID:   [MessageHandler(filters.TEXT & ~filters.COMMAND, tracking_admin_id)],
            ADMIN_TRACKING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tracking_admin_code)],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
    )

    discount_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 ارسال تخفیف$"), discount_start)],
        states={
            ADMIN_DISCOUNT_ID:  [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_id)],
            ADMIN_DISCOUNT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_send)],
        },
        fallbacks=[CommandHandler("cancel", conv_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(order_conv)
    app.add_handler(profile_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(tracking_conv)
    app.add_handler(discount_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 ربات شایلی شروع به کار کرد!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
