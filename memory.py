import os

from supabase import Client, create_client

MEMORY_LIMIT = 10              # تعداد تبادل (پرسش + پاسخ) برای هر کاربر
KEEP_ROWS = MEMORY_LIMIT * 2   # هر تبادل دو ردیف است

_client: Client | None = None


def _db() -> Client:
    global _client
    if _client is None:
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            raise RuntimeError("SUPABASE_URL یا SUPABASE_KEY تنظیم نشده است.")
        _client = create_client(url, key)
    return _client


def get_history(user_id: int) -> list[dict]:
    res = (
        _db()
        .table("chat_messages")
        .select("role, content")
        .eq("user_id", user_id)
        .order("id", desc=True)
        .limit(KEEP_ROWS)
        .execute()
    )
    rows = list(res.data or [])
    rows.reverse()  # از قدیمی به جدید
    return [{"role": r["role"], "content": r["content"]} for r in rows]


def save_exchange(user_id: int, user_text: str, answer: str) -> None:
    _db().table("chat_messages").insert([
        {"user_id": user_id, "role": "user", "content": user_text},
        {"user_id": user_id, "role": "assistant", "content": answer},
    ]).execute()
    _trim(user_id)


def _trim(user_id: int) -> None:
    """ردیف‌های قدیمی‌تر از KEEP_ROWS را پاک می‌کند."""
    res = (
        _db()
        .table("chat_messages")
        .select("id")
        .eq("user_id", user_id)
        .order("id", desc=True)
        .range(KEEP_ROWS, KEEP_ROWS + 500)
        .execute()
    )
    old_ids = [r["id"] for r in (res.data or [])]
    if old_ids:
        _db().table("chat_messages").delete().in_("id", old_ids).execute()


def count_exchanges(user_id: int) -> int:
    res = (
        _db()
        .table("chat_messages")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .execute()
    )
    return (res.count or 0) // 2


def clear_history(user_id: int) -> None:
    _db().table("chat_messages").delete().eq("user_id", user_id).execute()