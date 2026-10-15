import asyncio
import logging
import os

from keep_alive import run_in_background
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

import memory
from assistant import MAX_INPUT_CHARS, AssistantError, ai_assistant
from memory import MEMORY_LIMIT

load_dotenv()
TOKEN = os.getenv("TOKEN_BOT")

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

TELEGRAM_MAX_CHARS = 4096
SAFE_MARGIN = 100
MAX_FILE_BYTES = 200_000
MAX_HISTORY_CHARS = 30_000
SIGNATURE = "عمادم ⭐"


def split_text(text: str, size: int) -> list[str]:
    return [text[i:i + size] for i in range(0, len(text), size)]


def build_messages(history: list[dict], new_text: str) -> list[dict]:
    past = list(history)
    while past and sum(len(m["content"]) for m in past) + len(new_text) > MAX_HISTORY_CHARS:
        del past[:2]  # قدیمی‌ترین تبادل
    return past + [{"role": "user", "content": new_text}]


async def send_answer(update: Update, answer: str, remaining: int) -> None:
    if remaining > 0:
        footer = f"\n\n🧠 حافظه: {remaining} تبادل باقی‌مانده\n{SIGNATURE}"
    else:
        footer = f"\n\n🧠 حافظه پر است (قدیمی‌ترین پیام‌ها حذف می‌شوند)\n{SIGNATURE}"

    chunks = split_text(answer, TELEGRAM_MAX_CHARS - len(footer) - SAFE_MARGIN)
    for chunk in chunks[:-1]:
        await update.message.reply_text(chunk)
    await update.message.reply_text(chunks[-1] + footer)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "سلام! هر سؤالی داری بپرس، یا متن / فایل .txt بفرست و بگو چه کاری روش انجام بدم.\n"
        "دستور /help راهنماست."
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "• هر سؤال یا متنی را مستقیم بفرست\n"
        "• فایل .txt بفرست (حداکثر ۲۰۰ کیلوبایت، UTF-8)؛ توضیح زیر فایل (caption) را هم بنویس\n"
        "• /recap: خلاصه‌ی تبادل‌های ذخیره‌شده\n"
        "• /clear: پاک کردن حافظه‌ی گفتگو\n"
        "• /about: درباره‌ی ربات"
    )


async def about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "من یک ربات هوشمند فارسی‌زبان هستم که به سؤال‌هات جواب می‌دم و متن‌ها را برات پردازش می‌کنم."
    )


async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        await asyncio.to_thread(memory.clear_history, user_id)
    except Exception:
        logger.exception("خطا در پاک کردن حافظه")
        await update.message.reply_text("پاک کردن حافظه انجام نشد. دوباره امتحان کن.")
        return
    await update.message.reply_text("حافظه‌ی گفتگو پاک شد.")


async def recap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = update.effective_user.id
    try:
        history = await asyncio.to_thread(memory.get_history, user_id)
    except Exception:
        logger.exception("خطا در خواندن حافظه")
        await update.message.reply_text("خواندن حافظه انجام نشد.")
        return

    if not history:
        await update.message.reply_text("هنوز گفتگویی ثبت نشده.")
        return

    prompt = (
        "برای هر تبادل بالا (پرسش کاربر و پاسخ تو) یک خط بنویس با این قالب: "
        "«شماره. پرسش: ... | پاسخ: ...». هر بخش در حد یک جمله‌ی کوتاه باشه. "
        "فقط همین فهرست را بده."
    )
    await update.message.chat.send_action(ChatAction.TYPING)
    messages = build_messages(history, prompt)

    try:
        answer = await asyncio.to_thread(ai_assistant, messages)
    except AssistantError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return
    except Exception:
        logger.exception("خطای غیرمنتظره در recap")
        await update.message.reply_text("خطای غیرمنتظره. دوباره امتحان کن.")
        return

    for chunk in split_text(answer, TELEGRAM_MAX_CHARS - SAFE_MARGIN):
        await update.message.reply_text(chunk)


async def process_text(update: Update, user_text: str) -> None:
    user_id = update.effective_user.id
    user_text = user_text.strip()[:MAX_INPUT_CHARS]
    if not user_text:
        await update.message.reply_text("پیام خالی است.")
        return

    await update.message.chat.send_action(ChatAction.TYPING)

    try:
        history = await asyncio.to_thread(memory.get_history, user_id)
    except Exception:
        logger.exception("خطا در خواندن حافظه؛ بدون تاریخچه ادامه می‌دهیم")
        history = []

    messages = build_messages(history, user_text)

    try:
        answer = await asyncio.to_thread(ai_assistant, messages)
    except AssistantError as e:
        await update.message.reply_text(f"⚠️ {e}")
        return
    except Exception:
        logger.exception("خطای غیرمنتظره در پاسخ‌دهی")
        await update.message.reply_text("خطای غیرمنتظره. دوباره امتحان کن.")
        return

    # فقط بعد از پاسخ موفق ذخیره کن
    try:
        await asyncio.to_thread(memory.save_exchange, user_id, user_text, answer)
        used = await asyncio.to_thread(memory.count_exchanges, user_id)
    except Exception:
        logger.exception("خطا در ذخیره‌ی حافظه")
        await update.message.reply_text(f"{answer}\n\n⚠️ این تبادل ذخیره نشد.")
        return

    await send_answer(update, answer, MEMORY_LIMIT - used)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await process_text(update, update.message.text)


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    doc = update.message.document

    if doc.file_size and doc.file_size > MAX_FILE_BYTES:
        await update.message.reply_text("فایل خیلی بزرگ است (حداکثر ۲۰۰ کیلوبایت).")
        return

    tg_file = await doc.get_file()
    raw = bytes(await tg_file.download_as_bytearray())

    try:
        file_text = raw.decode("utf-8")
    except UnicodeDecodeError:
        await update.message.reply_text("فایل باید با انکودینگ UTF-8 ذخیره شده باشد.")
        return

    caption = (update.message.caption or "").strip()
    instruction = caption or "کاربر یک فایل فرستاده است. اگر دستور مشخصی نداده، بپرس چه کاری انجام بدم."
    await process_text(update, f"{instruction}\n\n---\n{file_text}")


def main() -> None:
    if not TOKEN:
        raise SystemExit("token_bot تنظیم نشده است.")
    if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
        raise SystemExit("SUPABASE_URL و SUPABASE_KEY تنظیم نشده‌اند.")

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .concurrent_updates(True)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("about", about))
    app.add_handler(CommandHandler("clear", clear))
    app.add_handler(CommandHandler("recap", recap))
    app.add_handler(MessageHandler(filters.Document.FileExtension("txt"), handle_document))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    run_in_background()   # وب‌سرور کوچک برای Back4app
    app.run_polling()


if __name__ == "__main__":
    main()