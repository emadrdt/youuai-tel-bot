import os

import requests
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL = "nvidia/nemotron-3-ultra-550b-a55b:free"
TIMEOUT_SECONDS = 60
MAX_OUTPUT_TOKENS = 1500
MAX_INPUT_CHARS = 20_000  # سقف طول هر پیام جدید کاربر

SYSTEM_PROMPT = (
    "تو یک دستیار هوش مصنوعی فارسی‌زبان و حرفه‌ای هستی. "
    "به سؤال‌ها دقیق و روان جواب بده. "
    "اگر کاربر متنی فرستاد و درخواستی درباره‌ی آن داشت "
    "(خلاصه، ترجمه، بازنویسی، نقد و...)، همان را انجام بده. "
    "اگر درخواست مشخص نبود، کوتاه بپرس چه کاری می‌خواهد."
    "همچنین یک متخصص و پژوهشگر حرفه ای و به روز برنامه نویسی خصوصا پایتون هستی"
)


class AssistantError(Exception):
    """خطایی که متنش مستقیم به کاربر نشون داده می‌شه."""


def ai_assistant(messages: list[dict]) -> str:
    """
    messages: لیستی از دیکشنری‌های {"role": ..., "content": ...}
    (تاریخچه‌ی گفتگو + پیام جدید کاربر). پیام system داخل تابع اضافه می‌شه.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise AssistantError("کلید API تنظیم نشده است.")

    try:
        response = requests.post(
            OPENROUTER_URL,
            headers={"Authorization": f"Bearer {api_key}"},
            json={
                "model": MODEL,
                "max_tokens": MAX_OUTPUT_TOKENS,
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}, *messages],
            },
            timeout=TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        raise AssistantError("ارتباط با سرویس هوش مصنوعی برقرار نشد.")

    if response.status_code == 429:
        raise AssistantError("سقف درخواست‌های رایگان پر شده. کمی بعد دوباره امتحان کن.")
    if response.status_code != 200:
        raise AssistantError(f"خطای سرویس (کد {response.status_code}).")

    try:
        content = response.json()["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError, ValueError):
        raise AssistantError("پاسخ نامعتبر از سرویس دریافت شد.")

    if not content or not content.strip():
        raise AssistantError("مدل پاسخی برنگرداند. دوباره امتحان کن.")

    return content.strip()