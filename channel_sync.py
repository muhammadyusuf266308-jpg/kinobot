# ============================================================
# channel_sync.py – Kanalni bot ichidan (online) o'qib, bazaga yuklash
#
# Ikki rejim (avtomatik tanlanadi):
#   1) TG_SESSION bor     → foydalanuvchi sessiyasi bilan butun tarix o'qiladi (eng ishonchli)
#   2) TG_SESSION yo'q    → bot tokeni bilan post ID lari bo'yicha (1, 2, 3, ...) o'qiladi
#                           (bot kanalda admin bo'lishi va API_ID/API_HASH berilgan bo'lishi kerak)
# ============================================================
import asyncio
import logging
import re
import time

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from telethon.sessions import StringSession

from channel_parser import is_placeholder_title, parse_post_multiple
from config import API_HASH, API_ID, BOT_TOKEN, CHANNEL_ID, TG_SESSION
from database import add_movies_bulk, get_max_channel_msg_id, get_saved_index

logger = logging.getLogger(__name__)

_HAS_CODE_RE = re.compile(r"(?i)\bk[io]d[a-z]*\b|\bcode\b")
_BATCH_IDS = 100        # bot rejimida bitta so'rovda nechta post ID
_STOP_AFTER_EMPTY = 500  # shuncha ketma-ket bo'sh ID dan keyin kanal tugagan deb hisoblanadi
_SAVE_EVERY = 100
_AI_DELAY = 0.7

_client: TelegramClient | None = None
_running = False


def is_running() -> bool:
    return _running


async def _get_client() -> TelegramClient:
    """Telethon klientini bir marta ulaydi va qayta ishlatadi (qayta-qayta login qilmaslik uchun)."""
    global _client
    if _client is not None and _client.is_connected():
        return _client

    if not API_ID or not API_HASH:
        raise RuntimeError(
            "API_ID va API_HASH sozlanmagan. my.telegram.org dan oling va "
            "hosting (Railway) o'zgaruvchilariga qo'shing."
        )

    if TG_SESSION:
        client = TelegramClient(StringSession(TG_SESSION), API_ID, API_HASH)
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect()
            raise RuntimeError("TG_SESSION eskirgan. make_session.py ni qayta ishga tushiring.")
    else:
        client = TelegramClient(StringSession(), API_ID, API_HASH)
        await client.start(bot_token=BOT_TOKEN)

    _client = client
    return client


def _channel_entity():
    cid = str(CHANNEL_ID).strip()
    return int(cid) if cid.lstrip("-").isdigit() else cid


async def _iter_posts(client: TelegramClient, entity):
    """Kanal postlarini eskidan yangiga qarab beradi."""
    if TG_SESSION:
        async for m in client.iter_messages(entity, reverse=True):
            yield m
        return

    # Bot rejimi: botlar tarixni o'qiy olmaydi, lekin ID bo'yicha post ola oladi.
    start = 1
    empty_run = 0
    while empty_run < _STOP_AFTER_EMPTY:
        ids = list(range(start, start + _BATCH_IDS))
        try:
            msgs = await client.get_messages(entity, ids=ids)
        except FloodWaitError as e:
            logger.warning(f"FloodWait: {e.seconds}s kutilmoqda")
            await asyncio.sleep(e.seconds + 1)
            continue
        found = False
        for m in msgs:
            if m is not None and getattr(m, "id", None):
                found = True
                yield m
        empty_run = 0 if found else empty_run + _BATCH_IDS
        start += _BATCH_IDS
        await asyncio.sleep(0.3)


async def sync_channel(deep_ai: bool = False, refresh: bool = False, progress=None) -> dict:
    """
    Kanalni boshidan oxirigacha aylanib chiqadi:
      • bazada bor postlarni o'tkazib yuboradi,
      • yangi postlardan kinolarni ajratib (parser, kerak bo'lsa AI) bazaga saqlaydi.
    deep_ai=True  bo'lsa, eski tushunilmagan postlar ham AI bilan tekshiriladi.
    refresh=True  bo'lsa, bazada bor postlar ham qaytadan tahlil qilinib, yozuvlar YANGILANADI
                  (parser yaxshilangandan keyin eski noto'g'ri nomlarni tuzatish uchun).
    """
    global _running
    if _running:
        raise RuntimeError("Sinxronizatsiya allaqachon ketmoqda.")
    _running = True
    started = time.time()
    stats = {"scanned": 0, "skipped_known": 0, "new": 0, "updated": 0, "ai_posts": 0,
             "duplicates": 0, "errors": 0, "seconds": 0,
             "by_type": {"kod": 0, "link": 0, "post": 0}}

    try:
        client = await _get_client()
        entity = _channel_entity()

        known_codes, known_msg_ids, placeholders = await asyncio.to_thread(get_saved_index)
        max_saved = await asyncio.to_thread(get_max_channel_msg_id)

        parse_ai = None
        buffer: list[dict] = []

        async def flush():
            nonlocal buffer
            if buffer:
                batch, buffer = buffer, []
                await asyncio.to_thread(add_movies_bulk, batch)

        async for m in _iter_posts(client, entity):
            text = getattr(m, "message", None) or ""
            if not text:
                continue
            stats["scanned"] += 1

            if m.id in known_msg_ids and not refresh:
                stats["skipped_known"] += 1
            else:
                try:
                    has_media = bool(getattr(m, "photo", None) or getattr(m, "video", None)
                                     or getattr(m, "document", None))
                    media_name = getattr(getattr(m, "file", None), "name", None)
                    movies = parse_post_multiple(text, message_id=m.id,
                                                 has_media=has_media, media_name=media_name)
                    used_ai = False

                    # AI faqat yangi postlarda (yoki /sync ai bilan hamma tushunilmaganlarda)
                    if not movies and _HAS_CODE_RE.search(text) and (deep_ai or m.id > max_saved):
                        if parse_ai is None:
                            from ai_service import parse_post_with_ai
                            parse_ai = parse_post_with_ai
                        movies = await parse_ai(text, message_id=m.id)
                        used_ai = bool(movies)
                        await asyncio.sleep(_AI_DELAY)

                    fresh = []
                    for mv in movies:
                        code = mv["bot_code"]
                        is_known = code in known_codes
                        if is_known and not refresh:
                            # Faqat vaqtincha nomli ("Kino #123") yozuv haqiqiy nom bilan almashtiriladi
                            if not (code in placeholders and not is_placeholder_title(mv["title"])):
                                stats["duplicates"] += 1
                                continue
                        # Qayta tahlilda haqiqiy nomni vaqtincha nom bilan almashtirib yubormaymiz
                        if is_known and refresh and is_placeholder_title(mv["title"]) \
                                and code not in placeholders:
                            stats["duplicates"] += 1
                            continue
                        if is_known:
                            stats["updated"] += 1
                        else:
                            stats["new"] += 1
                            kind = code.split(":", 1)[0].lower()
                            stats["by_type"][kind if kind in stats["by_type"] else "kod"] += 1
                        known_codes.add(code)
                        if is_placeholder_title(mv["title"]):
                            placeholders.add(code)
                        else:
                            placeholders.discard(code)
                        fresh.append(mv)

                    if fresh:
                        if used_ai:
                            stats["ai_posts"] += 1
                        buffer.extend(fresh)
                        if len(buffer) >= _SAVE_EVERY:
                            await flush()
                except Exception as e:
                    stats["errors"] += 1
                    logger.warning(f"Post #{m.id} xatosi: {e}")

            if progress and stats["scanned"] % 50 == 0:
                await progress(stats)

        await flush()
        stats["seconds"] = round(time.time() - started)
        logger.info(f"Sync tugadi: {stats}")
        return stats
    finally:
        _running = False