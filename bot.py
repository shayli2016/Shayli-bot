import logging
import os
import json
import asyncio
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    filters, ContextTypes, ConversationHandler, CallbackQueryHandler, JobQueue
)
import google.generativeai as genai

# ─── تنظیمات ───────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "YOUR_BOT_TOKEN")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "YOUR_GEMINI_KEY")
ADMIN_CHAT_ID  = os.environ.get("ADMIN_CHAT_ID", "YOUR_TELEGRAM_ID")
CHANNEL_LINK   = "https://t.me/shaylionlineshop"
BALE_LINK      = "http://ble.ir/shaylionlineshop"
PHONE          = "09040710470"
INSTAGRAM      = "https://www.instagram.com/shaylionlineshop"
DB_FILE        = "shayli_db.json"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ════════════════════════════════════════════════════════════
# دیتابیس ساده (JSON)
# ════════════════════════════════════════════════════════════
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

# ─── مراحل ثبت سفارش ──────────────────────────────────────
(
    ORDER_PRODUCT, ORDER_COUNTRY, ORDER_NAME,
    ORDER_PHONE, ORDER_ADDRESS, ORDER_POSTAL, ORDER_RECEIPT,
) = range(7)

# ─── مراحل ادمین ──────────────────────────────────────────
(ADMIN_BROADCAST, ADMIN_TRACKING_ID, ADMIN_TRACKING_CODE,
 ADMIN_DISCOUNT_ID, ADMIN_DISCOUNT_MSG) = range(10, 15)

# ─── مراحل پروفایل ────────────────────────────────────────
(PROFILE_NAME, PROFILE_BIRTHDAY) = range(20, 22)

# ════════════════════════════════════════════════════════════
# پرامپت هوش مصنوعی
# ════════════════════════════════════════════════════════════
SYSTEM_PROMPT = """
تو دستیار هوشمند آنلاین‌شاپ شایلی هستی 🌟 اسمت «شایلی» هست.

📌 اطلاعات فروشگاه:
- نام: آنلاین‌شاپ شایلی
- اینستاگرام: shaylionlineshop
- کانال تلگرام: t.me/shaylionlineshop
- کانال بله: ble.ir/shaylionlineshop
- شماره تماس اضطراری: 09040710470

🛍️ دسته‌بندی محصولات:
لوازم آرایشی، لوازم خانه، ورزشی، مردانه، زنانه، بچه‌گانه، کیف (همه نوع)، کفش (همه نوع)

🌍 کشورهای تامین:
امارات (عمده)، ترکیه، کانادا، آمریکا

⏰ زمان تحویل:
- ترکیه: ۲ تا ۴ هفته (بخاطر مشکلات پرواز در شرایط فعلی)
- امارات: ۴ تا ۷ هفته (بخاطر مشکلات ارسال در شرایط فعلی) — در شرایط عادی ۵ تا ۸ هفته
- در زمان حراج ممکنه بیشتر بشه

💰 هزینه باربری امارات:
- لباس و اکسسوری: هر ۱۰۰ گرم = ۹۹,۰۰۰ تومان
- کفش: جفتی ۶۵۰,۰۰۰ تومان
- کیف: دانه‌ای ۶۰۰,۰۰۰ تومان
- هزینه باربری بعد از رسیدن سفارش اعلام میشه

💰 هزینه باربری ترکیه:
- هوایی: هر ۱۰۰ گرم = ۵۸,۰۰۰ تومان
- بعد از رسیدن وزن میشه و هزینه اعلام میشه

💳 پرداخت:
- روش: کارت به کارت
- شماره کارت بعد از تأیید از ادمین گرفته میشه
- اول هزینه خود محصول پرداخت میشه، باربری بعد از رسیدن

📦 ارسال داخلی:
- تیپاکس (درب منزل) یا پست
- هزینه پیک/پست بعد از رسیدن سفارش اعلام میشه

❌ کنسلی و تعویض:
- تعویض و کنسلی نداریم (آنلاین‌شاپیم)
- اگه محصول آسیب‌دیده یا اشتباه رسید: تا ۴۸ ساعت عکس واضح بفرست
- همه سفارشات قبل از ارسال چک و عکس گرفته میشه

📦 موجودی:
- اگه روی محصول نوشته «موجود در ایران» یعنی موجوده
- اگه ننوشته یعنی سفارشیه

🔍 برای دیدن محصولات:
مشتری رو به کانال تلگرام هدایت کن: t.me/shaylionlineshop

قوانین پاسخگویی:
- همیشه صمیمی و دوستانه باش، از «شما» استفاده کن
- از ایموجی مناسب استفاده کن
- برای قیمت محصول بگو از ادمین بپرسن
- اگه سوالی بود که جواب نداری بگو: «این سوالو برای ادمین میفرستم، پیام بده جواب بگیری 🙏»
- پیام‌هات کوتاه و مفید باشه
- برای ثبت سفارش بگو دکمه «🛍️ ثبت سفارش» رو بزنن
"""

# ════════════════════════════════════════════════════════════
# کیبوردها
# ════════════════════════════════════════════════════════════
def main_keyboard():
    keyboard = [
        [KeyboardButton("🛍️ ثبت سفارش"), KeyboardButton("🔍 جستجو محصول")],
        [KeyboardButton("📦 پیگیری سفارش"), KeyboardButton("❓ سوالات متداول")],
        [KeyboardButton("📞 ارتباط با ما"), KeyboardButton("👤 پروفایل من")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_keyboard():
    keyboard = [
        [KeyboardButton("📢 پیام همگانی"), KeyboardButton("📦 ثبت کد پیگیری")],
        [KeyboardButton("🎁 ارسال تخفیف"), KeyboardButton("📊 آمار ربات")],
        [KeyboardButton("🔙 خروج از پنل")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def country_keyboard():
    keyboard = [
        [KeyboardButton("🇦🇪 امارات"), KeyboardButton("🇹🇷 ترکیه")],
        [KeyboardButton("🇨🇦 کانادا"), KeyboardButton("🇺🇸 آمریکا")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

# ════════════════════════════════════════════════════════════
# هوش مصنوعی
# ════════════════════════════════════════════════════════════
async def ask_ai(user_message: str, history: list) -> str:
    try:
        chat = model.start_chat(history=history)
        response = chat.send_message(
            f"{SYSTEM_PROMPT}\n\nپیام مشتری: {user_message}"
        )
        return response.text
    except Exception as e:
        logger.error(f"Gemini error: {e}")
        return "عزیزم یه مشکل کوچیک پیش اومد 😅 لطفاً دوباره امتحان کن یا مستقیم پیام بده."

# ════════════════════════════════════════════════════════════
# /start
# ════════════════════════════════════════════════════════════
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_user.id
    db = load_db()
    user = get_user(db, chat_id)

    # ثبت کاربر جدید
    if not user:
        user = {
            "chat_id": chat_id,
            "first_name": update.effective_user.first_name or "",
            "username": update.effective_user.username or "",
            "joined": datetime.now().isoformat(),
            "last_active": datetime.now().isoformat(),
            "full_name": "",
            "birthday": "",
            "orders": []
        }
        save_user(db, chat_id, user)
    else:
        user["last_active"] = datetime.now().isoformat()
        save_user(db, chat_id, user)

    context.user_data["history"] = []
    name = update.effective_user.first_name or "عزیزم"

    await update.message.reply_text(
        f"سلام {name} جان! 👋\n\n"
        "به آنلاین‌شاپ شایلی خوش اومدی 🌟\n"
        "بهترین محصولات از امارات، ترکیه، کانادا و آمریکا 🛒\n\n"
        "چطور می‌تونم کمکت کنم؟ 😊",
        reply_markup=main_keyboard()
    )

# ════════════════════════════════════════════════════════════
# پروفایل
# ════════════════════════════════════════════════════════════
async def profile_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    user = get_user(db, update.effective_user.id)
    name = user.get("full_name", "")
    bday = user.get("birthday", "")

    if name and bday:
        await update.message.reply_text(
            f"👤 *پروفایل شما*\n\n"
            f"📛 نام: {name}\n"
            f"🎂 تولد: {bday}\n\n"
            f"برای ویرایش، نام کاملت رو بنویس:",
            parse_mode="Markdown",
            reply_markup=ReplyKeyboardRemove()
        )
    else:
        await update.message.reply_text(
            "👤 بذار پروفایلت رو کامل کنیم!\n\n"
            "اسم و فامیلت رو بنویس 👇",
            reply_markup=ReplyKeyboardRemove()
        )
    return PROFILE_NAME

async def profile_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["profile_name"] = update.message.text
    await update.message.reply_text(
        "🎂 تاریخ تولدت رو بنویس:\n"
        "_(فرمت: روز/ماه مثلاً ۱۵/۶)_",
        parse_mode="Markdown"
    )
    return PROFILE_BIRTHDAY

async def profile_birthday(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    chat_id = update.effective_user.id
    user = get_user(db, chat_id)
    user["full_name"] = context.user_data["profile_name"]
    user["birthday"] = update.message.text
    save_user(db, chat_id, user)

    await update.message.reply_text(
        "✅ پروفایلت ذخیره شد!\n\n"
        f"📛 نام: {user['full_name']}\n"
        f"🎂 تولد: {user['birthday']}\n\n"
        "روز تولدت بهت تبریک میگم و کد تخفیف ویژه میفرستم 🎉",
        reply_markup=main_keyboard()
    )
    return ConversationHandler.END

async def profile_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("برگشتیم 😊", reply_markup=main_keyboard())
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
# ثبت سفارش
# ════════════════════════════════════════════════════════════
async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"] = {}
    await update.message.reply_text(
        "🛍️ *ثبت سفارش شایلی*\n\n"
        "عالیه! بریم سفارشت رو ثبت کنیم 😊\n\n"
        "اول بگو *از کدوم کشور* می‌خوای سفارش بدی؟",
        parse_mode="Markdown",
        reply_markup=country_keyboard()
    )
    return ORDER_COUNTRY

async def order_country(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["country"] = update.message.text
    await update.message.reply_text(
        "✅ ثبت شد!\n\n"
        "حالا *محصولی که می‌خوای* رو توضیح بده 👇\n"
        "_(لینک، عکس، اسم برند، رنگ، سایز — هر چیزی که داری)_",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return ORDER_PRODUCT

async def order_product(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        context.user_data["order"]["product"] = f"[عکس محصول - {update.message.photo[-1].file_id}]"
        if update.message.caption:
            context.user_data["order"]["product"] += f" | توضیح: {update.message.caption}"
    elif update.message.text:
        context.user_data["order"]["product"] = update.message.text
    await update.message.reply_text(
        "👌 ثبت شد!\n\n*نام و نام خانوادگی* کاملت رو بنویس 👇",
        parse_mode="Markdown"
    )
    return ORDER_NAME

async def order_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["name"] = update.message.text
    await update.message.reply_text(
        "📱 شماره موبایلت رو وارد کن:",
        parse_mode="Markdown"
    )
    return ORDER_PHONE

async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not (phone.startswith("09") and len(phone) == 11 and phone.isdigit()):
        await update.message.reply_text("⚠️ شماره باید با ۰۹ شروع بشه و ۱۱ رقم باشه. دوباره بنویس:")
        return ORDER_PHONE
    context.user_data["order"]["phone"] = phone
    await update.message.reply_text(
        "📍 آدرس کامل رو بنویس:\n_(استان، شهر، خیابان، پلاک، واحد)_",
        parse_mode="Markdown"
    )
    return ORDER_ADDRESS

async def order_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["order"]["address"] = update.message.text
    await update.message.reply_text("📮 کد پستی ۱۰ رقمی:")
    return ORDER_POSTAL

async def order_postal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    postal = update.message.text.strip()
    if not (len(postal) == 10 and postal.isdigit()):
        await update.message.reply_text("⚠️ کد پستی باید ۱۰ رقم باشه. دوباره بنویس:")
        return ORDER_POSTAL
    context.user_data["order"]["postal"] = postal

    order = context.user_data["order"]
    await update.message.reply_text(
        f"🧾 *خلاصه سفارش:*\n\n"
        f"🌍 کشور: {order['country']}\n"
        f"📦 محصول: {order['product']}\n"
        f"👤 نام: {order['name']}\n"
        f"📱 موبایل: {order['phone']}\n"
        f"📍 آدرس: {order['address']}\n"
        f"📮 کد پستی: {order['postal']}\n\n"
        f"💳 *مرحله آخر: پرداخت*\n"
        f"برای دریافت شماره کارت به ادمین پیام بده.\n"
        f"بعد از پرداخت، *فیش واریزی* رو اینجا بفرست 👇",
        parse_mode="Markdown"
    )
    return ORDER_RECEIPT

async def order_receipt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        receipt_info = f"[عکس فیش - {update.message.photo[-1].file_id}]"
    elif update.message.document:
        receipt_info = f"[فایل فیش - {update.message.document.file_id}]"
    elif update.message.text:
        receipt_info = update.message.text
    else:
        await update.message.reply_text("⚠️ لطفاً عکس یا متن فیش رو بفرست.")
        return ORDER_RECEIPT

    db = load_db()
    order_id = f"SH{db['order_counter']}"
    db["order_counter"] += 1

    chat_id = update.effective_user.id
    order = context.user_data["order"]
    order["receipt"] = receipt_info
    order["order_id"] = order_id
    order["date"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    order["status"] = "در انتظار بررسی"
    order["chat_id"] = chat_id

    db["orders"].append(order)

    user = get_user(db, chat_id)
    if "orders" not in user:
        user["orders"] = []
    user["orders"].append(order_id)
    user["last_order"] = datetime.now().isoformat()
    save_user(db, chat_id, user)
    save_db(db)

    # اطلاع به ادمین
    user_tg = update.effective_user
    admin_msg = (
        f"🔔 *سفارش جدید شایلی!*\n\n"
        f"🆔 کد سفارش: `{order_id}`\n"
        f"👤 کاربر: {user_tg.first_name} (@{user_tg.username or 'ندارد'})\n"
        f"🆔 Chat ID: `{chat_id}`\n\n"
        f"🌍 کشور: {order['country']}\n"
        f"📦 محصول: {order['product']}\n"
        f"👤 نام: {order['name']}\n"
        f"📱 موبایل: {order['phone']}\n"
        f"📍 آدرس: {order['address']}\n"
        f"📮 کد پستی: {order['postal']}\n"
        f"🧾 فیش: {order['receipt']}"
    )
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=admin_msg, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Admin notify error: {e}")

    await update.message.reply_text(
        f"✅ *سفارشت با موفقیت ثبت شد!*\n\n"
        f"🎉 کد سفارش شما: `{order_id}`\n"
        f"این کد رو نگه‌دار برای پیگیری 📌\n\n"
        f"مدیر فروشگاه در اسرع وقت بررسی می‌کنه 📲\n\n"
        f"━━━━━━━━━━━━━━\n"
        f"📣 دوستان برای دسترسی به اینترنت، حتماً در کانال بله ما عضو بشید:\n"
        f"👇\n{BALE_LINK}",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )
    context.user_data["order"] = {}
    return ConversationHandler.END

async def order_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ ثبت سفارش لغو شد.\nهر وقت خواستی دوباره امتحان کن! 😊", reply_markup=main_keyboard())
    return ConversationHandler.END

# ════════════════════════════════════════════════════════════
# پیگیری سفارش
# ════════════════════════════════════════════════════════════
async def tracking_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    chat_id = str(update.effective_user.id)
    user = get_user(db, update.effective_user.id)

    if not user.get("orders"):
        await update.message.reply_text(
            "📦 *پیگیری سفارش*\n\n"
            "سفارشی برای شما ثبت نشده.\n"
            "اگه فکر می‌کنی اشتباهیه، کد سفارشت رو بنویس 👇",
            parse_mode="Markdown"
        )
        return

    order_ids = user.get("orders", [])
    msg = "📦 *سفارش‌های شما:*\n\n"
    for oid in order_ids[-5:]:
        for o in db["orders"]:
            if o.get("order_id") == oid:
                msg += (
                    f"🔖 کد: `{oid}`\n"
                    f"📅 تاریخ: {o.get('date', '-')}\n"
                    f"🌍 کشور: {o.get('country', '-')}\n"
                    f"📊 وضعیت: {o.get('status', 'در انتظار بررسی')}\n"
                )
                if o.get("tracking_code"):
                    msg += f"🚚 کد پیگیری: `{o['tracking_code']}`\n"
                msg += "━━━━━━━━\n"

    await update.message.reply_text(msg, parse_mode="Markdown", reply_markup=main_keyboard())

# ════════════════════════════════════════════════════════════
# پنل ادمین
# ════════════════════════════════════════════════════════════
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        await update.message.reply_text("⛔ دسترسی ندارید.")
        return
    db = load_db()
    total_users = len(db["users"])
    total_orders = len(db["orders"])
    await update.message.reply_text(
        f"👑 *پنل مدیریت شایلی*\n\n"
        f"👥 کل کاربران: {total_users}\n"
        f"🛍️ کل سفارشات: {total_orders}\n\n"
        f"از منوی زیر انتخاب کن:",
        parse_mode="Markdown",
        reply_markup=admin_keyboard()
    )

# ─── پیام همگانی ──────────────────────────────────────────
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        return
    await update.message.reply_text(
        "📢 *پیام همگانی*\n\nمتن پیامی که میخوای به همه بفرستی رو بنویس:",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADMIN_BROADCAST

async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    msg = update.message.text
    sent = 0
    failed = 0
    for uid in db["users"]:
        try:
            await context.bot.send_message(chat_id=int(uid), text=f"📢 *پیام از شایلی:*\n\n{msg}", parse_mode="Markdown")
            sent += 1
            await asyncio.sleep(0.05)
        except:
            failed += 1
    await update.message.reply_text(
        f"✅ پیام فرستاده شد!\n✔️ موفق: {sent}\n❌ ناموفق: {failed}",
        reply_markup=admin_keyboard()
    )
    return ConversationHandler.END

# ─── ثبت کد پیگیری ────────────────────────────────────────
async def tracking_admin_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        return
    await update.message.reply_text(
        "📦 *ثبت کد پیگیری*\n\nکد سفارش رو بنویس (مثلاً SH1001):",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADMIN_TRACKING_ID

async def tracking_admin_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["tracking_order_id"] = update.message.text.strip()
    await update.message.reply_text("کد تیپاکس / ماهکس / پست رو بنویس:")
    return ADMIN_TRACKING_CODE

async def tracking_admin_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    order_id = context.user_data["tracking_order_id"]
    tracking_code = update.message.text.strip()
    found = False
    for o in db["orders"]:
        if o.get("order_id") == order_id:
            o["tracking_code"] = tracking_code
            o["status"] = "ارسال شده 🚚"
            found = True
            # اطلاع به مشتری
            try:
                await context.bot.send_message(
                    chat_id=o["chat_id"],
                    text=f"🚚 *سفارش شما ارسال شد!*\n\n"
                         f"🔖 کد سفارش: `{order_id}`\n"
                         f"📮 کد پیگیری: `{tracking_code}`\n\n"
                         f"از طریق سایت تیپاکس یا ماهکس پیگیری کنید 😊",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Notify error: {e}")
            break
    save_db(db)
    if found:
        await update.message.reply_text(f"✅ کد پیگیری برای {order_id} ثبت شد و به مشتری اطلاع داده شد!", reply_markup=admin_keyboard())
    else:
        await update.message.reply_text(f"❌ سفارشی با کد {order_id} پیدا نشد.", reply_markup=admin_keyboard())
    return ConversationHandler.END

# ─── ارسال تخفیف ──────────────────────────────────────────
async def discount_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        return
    db = load_db()
    users_list = ""
    for i, (uid, u) in enumerate(list(db["users"].items())[:20]):
        users_list += f"{i+1}. {u.get('full_name') or u.get('first_name', uid)} - `{uid}`\n"
    await update.message.reply_text(
        f"🎁 *ارسال تخفیف*\n\nChat ID مشتری رو بنویس:\n\n{users_list}",
        parse_mode="Markdown",
        reply_markup=ReplyKeyboardRemove()
    )
    return ADMIN_DISCOUNT_ID

async def discount_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["discount_chat_id"] = update.message.text.strip()
    await update.message.reply_text("متن پیام تخفیف رو بنویس:\n_(مثلاً: امروز می‌تونی بدون سود ثبت کنی!)_", parse_mode="Markdown")
    return ADMIN_DISCOUNT_MSG

async def discount_send(update: Update, context: ContextTypes.DEFAULT_TYPE):
    target_id = context.user_data["discount_chat_id"]
    msg = update.message.text
    try:
        await context.bot.send_message(
            chat_id=int(target_id),
            text=f"🎁 *پیام ویژه از شایلی:*\n\n{msg}\n\nبرای استفاده پیام بده به ادمین 😊",
            parse_mode="Markdown"
        )
        await update.message.reply_text("✅ پیام تخفیف فرستاده شد!", reply_markup=admin_keyboard())
    except Exception as e:
        await update.message.reply_text(f"❌ خطا: {e}", reply_markup=admin_keyboard())
    return ConversationHandler.END

async def admin_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لغو شد.", reply_markup=admin_keyboard())
    return ConversationHandler.END

# ─── آمار ─────────────────────────────────────────────────
async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_user.id) != str(ADMIN_CHAT_ID):
        return
    db = load_db()
    total_users = len(db["users"])
    total_orders = len(db["orders"])
    pending = sum(1 for o in db["orders"] if o.get("status") == "در انتظار بررسی")
    sent = sum(1 for o in db["orders"] if "ارسال" in o.get("status", ""))
    await update.message.reply_text(
        f"📊 *آمار ربات شایلی*\n\n"
        f"👥 کل کاربران: {total_users}\n"
        f"🛍️ کل سفارشات: {total_orders}\n"
        f"⏳ در انتظار بررسی: {pending}\n"
        f"🚚 ارسال شده: {sent}",
        parse_mode="Markdown",
        reply_markup=admin_keyboard()
    )

async def exit_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("برگشتیم به منوی اصلی 😊", reply_markup=main_keyboard())

# ════════════════════════════════════════════════════════════
# جاب‌های خودکار (یادآوری + تولد)
# ════════════════════════════════════════════════════════════
async def check_birthdays(context: ContextTypes.DEFAULT_TYPE):
    db = load_db()
    today = datetime.now()
    today_str = f"{today.day}/{today.month}"
    for uid, user in db["users"].items():
        bday = user.get("birthday", "")
        if bday == today_str:
            name = user.get("full_name") or user.get("first_name", "عزیزم")
            try:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"🎂 *تولدت مبارک {name} جان!*\n\n"
                         f"🎉 شایلی برات آرزوی بهترین‌ها رو داره!\n\n"
                         f"🎁 امروز می‌تونی *بدون سود* ثبت سفارش کنی!\n"
                         f"فقط پیام بده به ادمین و بگو تولدمه 😊\n\n"
                         f"📞 {PHONE}",
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"Birthday error {uid}: {e}")

async def check_incomplete_orders(context: ContextTypes.DEFAULT_TYPE):
    """یادآوری به کسایی که ثبت سفارش رو نصفه رها کردن"""
    db = load_db()
    now = datetime.now()
    for uid, user in db["users"].items():
        last_active = user.get("last_active", "")
        last_order = user.get("last_order", "")
        if not last_active:
            continue
        try:
            last_dt = datetime.fromisoformat(last_active)
            # اگه ۲ ساعته فعاله ولی سفارش نداده
            if (now - last_dt).total_seconds() > 7200 and not last_order:
                await context.bot.send_message(
                    chat_id=int(uid),
                    text="سلام! 👋 یادم افتادی 😊\n\n"
                         "میدونم داشتی ثبت سفارش می‌کردی، اگه سوالی داری یا کمک خواستی اینجام!\n\n"
                         "برای ثبت سفارش دکمه رو بزن 🛍️",
                    reply_markup=main_keyboard()
                )
                user["last_active"] = now.isoformat()
                save_user(db, int(uid), user)
        except:
            pass

async def check_inactive_users(context: ContextTypes.DEFAULT_TYPE):
    """یادآوری به مشتریایی که مدتیه سفارش ندادن"""
    db = load_db()
    now = datetime.now()
    for uid, user in db["users"].items():
        last_order = user.get("last_order", "")
        if not last_order:
            continue
        try:
            last_dt = datetime.fromisoformat(last_order)
            # اگه ۳۰ روزه سفارش نداده
            if (now - last_dt).days >= 30:
                name = user.get("full_name") or user.get("first_name", "عزیزم")
                await context.bot.send_message(
                    chat_id=int(uid),
                    text=f"سلام {name} جان! 🌟\n\n"
                         f"مدتیه ندیدمت 😊\n"
                         f"محصولات جدیدی از امارات و ترکیه داریم!\n"
                         f"سر بزن به کانالمون 👇\n{CHANNEL_LINK}",
                )
                user["last_order"] = now.isoformat()
                save_user(db, int(uid), user)
        except:
            pass

# ════════════════════════════════════════════════════════════
# سوالات متداول
# ════════════════════════════════════════════════════════════
FAQ_TEXT = """
❓ *سوالات متداول شایلی*

⏰ *زمان تحویل:*
• ترکیه: ۲ تا ۴ هفته (شرایط فعلی)
• امارات: ۴ تا ۷ هفته (شرایط فعلی)
• در زمان حراج ممکنه بیشتر بشه

💰 *هزینه باربری امارات:*
• لباس و اکسسوری: هر ۱۰۰گرم = ۹۹,۰۰۰ت
• کفش: جفتی ۶۵۰,۰۰۰ت
• کیف: دانه‌ای ۶۰۰,۰۰۰ت

💰 *هزینه باربری ترکیه:*
• هر ۱۰۰گرم = ۵۸,۰۰۰ت (هوایی)

💳 *پرداخت:*
اول هزینه محصول (کارت به کارت)
باربری بعد از رسیدن اعلام میشه

❌ *تعویض و مرجوعی:*
تعویض نداریم. اگه محصول آسیب‌دیده یا اشتباه بود تا ۴۸ساعت عکس بفرست

📦 *موجودی:*
اگه «موجود در ایران» نوشته = موجود
اگه ننوشته = سفارشیه
"""

async def faq_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(FAQ_TEXT, parse_mode="Markdown", reply_markup=main_keyboard())

# ════════════════════════════════════════════════════════════
# ارتباط با ما
# ════════════════════════════════════════════════════════════
async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📞 *ارتباط با شایلی*\n\n"
        f"📱 شماره تماس اضطراری: `{PHONE}`\n\n"
        f"📣 کانال تلگرام:\n{CHANNEL_LINK}\n\n"
        f"📸 اینستاگرام:\n{INSTAGRAM}\n\n"
        f"🔵 کانال بله:\n{BALE_LINK}\n\n"
        f"⏰ پاسخگویی: شنبه تا پنجشنبه ۱۰ صبح تا ۱۰ شب",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ════════════════════════════════════════════════════════════
# جستجو محصول
# ════════════════════════════════════════════════════════════
async def search_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔍 *جستجوی محصول*\n\n"
        "برای دیدن همه محصولات کانال ما رو چک کن 👇\n"
        f"{CHANNEL_LINK}\n\n"
        "هر محصولی که خواستی لینکش یا عکسش رو برام بفرست تا ثبت کنم 🛍️\n\n"
        "💡 اگه روی محصول نوشته *«موجود در ایران»* یعنی الان موجوده\n"
        "اگه ننوشته یعنی سفارشیه و از کشور مبدأ میاد",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

# ════════════════════════════════════════════════════════════
# پیام‌های عادی → هوش مصنوعی
# ════════════════════════════════════════════════════════════
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text if update.message.text else ""

    # دکمه‌های منو
    if text == "❓ سوالات متداول":
        return await faq_handler(update, context)
    if text == "📞 ارتباط با ما":
        return await contact_handler(update, context)
    if text == "📦 پیگیری سفارش":
        return await tracking_handler(update, context)
    if text == "🔍 جستجو محصول":
        return await search_handler(update, context)
    if text == "📊 آمار ربات":
        return await stats_handler(update, context)
    if text == "🔙 خروج از پنل":
        return await exit_admin(update, context)

    # آپدیت last_active
    db = load_db()
    uid = update.effective_user.id
    user = get_user(db, uid)
    if user:
        user["last_active"] = datetime.now().isoformat()
        save_user(db, uid, user)

    # هوش مصنوعی
    if "history" not in context.user_data:
        context.user_data["history"] = []

    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    reply = await ask_ai(text, context.user_data["history"])

    context.user_data["history"].append({"role": "user", "parts": [text]})
    context.user_data["history"].append({"role": "model", "parts": [reply]})
    if len(context.user_data["history"]) > 20:
        context.user_data["history"] = context.user_data["history"][-20:]

    await update.message.reply_text(reply, reply_markup=main_keyboard())

# ════════════════════════════════════════════════════════════
# اجرا
# ════════════════════════════════════════════════════════════
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    # ثبت سفارش
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
        fallbacks=[CommandHandler("cancel", order_cancel)],
    )

    # پروفایل
    profile_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^👤 پروفایل من$"), profile_start)],
        states={
            PROFILE_NAME:     [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_name)],
            PROFILE_BIRTHDAY: [MessageHandler(filters.TEXT & ~filters.COMMAND, profile_birthday)],
        },
        fallbacks=[CommandHandler("cancel", profile_cancel)],
    )

    # پنل ادمین
    broadcast_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📢 پیام همگانی$"), broadcast_start)],
        states={ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, broadcast_send)]},
        fallbacks=[CommandHandler("cancel", admin_cancel)],
    )

    tracking_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📦 ثبت کد پیگیری$"), tracking_admin_start)],
        states={
            ADMIN_TRACKING_ID:   [MessageHandler(filters.TEXT & ~filters.COMMAND, tracking_admin_id)],
            ADMIN_TRACKING_CODE: [MessageHandler(filters.TEXT & ~filters.COMMAND, tracking_admin_code)],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel)],
    )

    discount_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^🎁 ارسال تخفیف$"), discount_start)],
        states={
            ADMIN_DISCOUNT_ID:  [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_id)],
            ADMIN_DISCOUNT_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, discount_send)],
        },
        fallbacks=[CommandHandler("cancel", admin_cancel)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(order_conv)
    app.add_handler(profile_conv)
    app.add_handler(broadcast_conv)
    app.add_handler(tracking_conv)
    app.add_handler(discount_conv)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # جاب‌های خودکار
    job_queue = app.job_queue
    job_queue.run_daily(check_birthdays, time=datetime.strptime("09:00", "%H:%M").time())
    job_queue.run_repeating(check_incomplete_orders, interval=3600, first=60)
    job_queue.run_daily(check_inactive_users, time=datetime.strptime("12:00", "%H:%M").time())

    logger.info("🤖 ربات شایلی شروع به کار کرد!")
    app.run_polling()

if __name__ == "__main__":
    main()
