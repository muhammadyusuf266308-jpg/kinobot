# ============================================================
#  bot.py  –  Asosiy Telegram bot (Yangilangan versiya)
#  Admin uchun qulay Kino qo'shish paneli bilan
# ============================================================
import logging
import re
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    ForceReply
)
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, ContextTypes, filters
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

from config import (
    BOT_TOKEN, ADMIN_ID, CHANNEL_ID, GROUP_ID,
    TRIGGER_WORDS
)
from database import (
    init_db, search_movie, add_movie, log_search,
    get_all_movies, delete_movie, movie_exists_by_code, get_stats,
    get_client
)
from channel_parser import parse_post, parse_post_multiple

# ─── Logging ─────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s │ %(levelname)s │ %(name)s │ %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

INSTAGRAM_RE = re.compile(
    r"(https?://)?(www\.)?(instagram\.com|instagr\.am)(/[^\s]*)?",
    re.IGNORECASE
)

BOT_USERNAME = "UzKinoMov1eBot"   # @ siz

# ─── Admin Kino qo'shish holatlari (ConversationHandler) ──────
(
    ADD_TITLE,
    ADD_CODE,
    ADD_YEAR,
    ADD_GENRE,
    ADD_DESC,
    ADD_MSG_ID
) = range(6)


# ─── Yordamchilar ────────────────────────────────────────────

def is_instagram(text: str) -> bool:
    return bool(INSTAGRAM_RE.search(text))


def clean_query(text: str) -> str:
    t = text.strip()
    colon = re.match(r"^[\w\s]{1,15}:\s*(.+)$", t)
    if colon:
        t = colon.group(1).strip()
    for word in TRIGGER_WORDS:
        t = re.sub(
            rf"^[!/]?{re.escape(word)}\s*[:,\-]?\s*", "", t, flags=re.IGNORECASE
        ).strip()
    endings = [
        r"\s+borm[ia]\??$", r"\s+bormi\??$", r"\s+kinosi\??$",
        r"\s+filmini?\??$", r"\s+seriali?\??$", r"\?+$",
    ]
    for end in endings:
        t = re.sub(end, "", t, flags=re.IGNORECASE).strip()
    return t or text.strip()


def movie_card(m: dict) -> str:
    lines = ["🎬 <b>Kino topildi!</b>\n"]
    name = m["title"]
    if m.get("title_ru"):
        name += f" / {m['title_ru']}"
    lines.append(f"🎬 <b>Nomi:</b> {name}")
    if m.get("year"):
        lines.append(f"📅 <b>Yili:</b> {m['year']}")
    if m.get("genre"):
        lines.append(f"🇺🇿 <b>Tili:</b> {m['genre']}")
    if m.get("description"):
        lines.append(f"\n{m['description']}")
    lines.append(f"\n📥 <b>Kino olish uchun botga yuboring:</b>")
    lines.append(f"<code>{m['bot_code']}</code>")
    lines.append(f"🤖 @{BOT_USERNAME}")
    return "\n".join(lines)


def mention(user) -> str:
    if user.username:
        return f"@{user.username}"
    return f'<a href="tg://user?id={user.id}">{user.full_name or "Foydalanuvchi"}</a>'


def is_our_channel(chat) -> bool:
    cid = str(CHANNEL_ID).strip().lstrip("@")
    return (
        str(chat.id) == str(CHANNEL_ID)
        or str(getattr(chat, "username", "") or "").lstrip("@") == cid
    )


def search_button() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔍 Kino qidirish", callback_data="search_ask")
    ]])


def admin_keyboard() -> InlineKeyboardMarkup:
    """Admin uchun boshqaruv tugmalari"""
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("➕ Yangi kino qo'shish", callback_data="admin_add_movie")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
         InlineKeyboardButton("📋 Kinolar ro'yxati", callback_data="admin_list")],
        [InlineKeyboardButton("📢 Guruhga qidiruv tugmasini yuborish", callback_data="admin_send_panel")]
    ])


# ═══════════════════════════════════════════════════════════════
#  CALLBACK: Tugmalar bosilganda
# ═══════════════════════════════════════════════════════════════

async def on_callback_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # Guruhdagi qidiruv tugmasi
    if data == "search_ask":
        await ctx.bot.send_message(
            chat_id=q.message.chat_id,
            text=(
                "🔍 <b>Kino qidirish:</b>\n"
                "Ushbu xabarga <b>Javob berish (Reply)</b> qilib, kino nomini yoki kodini yozing!\n\n"
                "Masalan: <code>Tor</code>, <code>Spartak</code>, <code>209</code>"
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=ForceReply(
                selective=False,
                input_field_placeholder="Kino nomini yozing..."
            )
        )
        return

    # Faqat admin uchun tugmalar
    if q.from_user.id != ADMIN_ID:
        return

    if data == "admin_stats":
        s = get_stats()
        rate = f"{s['found_count']/s['total_searches']*100:.1f}%" if s["total_searches"] else "—"
        await q.message.reply_html(
            f"📊 <b>Statistika</b>\n\n"
            f"🎬 Kinolar: <b>{s['total_movies']}</b>\n"
            f"🔍 Qidiruvlar: <b>{s['total_searches']}</b>\n"
            f"✅ Topildi: <b>{s['found_count']}</b>\n"
            f"❌ Topilmadi: <b>{s['not_found']}</b>\n"
            f"📈 Muvaffaqiyat: <b>{rate}</b>"
        )
    elif data == "admin_list":
        movies = get_all_movies()
        if not movies:
            await q.message.reply_text("📭 Bazada kinolar yo'q.")
            return
        text = f"🎬 <b>Jami {len(movies)} ta kino:</b>\n\n"
        for m in movies[:20]:
            yr = f" ({m['year']})" if m.get("year") else ""
            text += f"<code>{m['id']:>4}</code>  {m['title']}{yr}  → <code>{m['bot_code']}</code>\n"
        if len(movies) > 20:
            text += f"\n... va yana {len(movies)-20} ta."
        await q.message.reply_html(text)
    elif data == "admin_send_panel":
        if GROUP_ID:
            try:
                await ctx.bot.send_message(
                    chat_id=GROUP_ID,
                    text=(
                        "🎬 <b>Kino qidirish</b>\n\n"
                        "Quyidagi tugmani bosing, kino nomini yozing\n"
                        "va <b>Jo'natish</b> tugmasini bosing! 👇"
                    ),
                    reply_markup=search_button(),
                    parse_mode=ParseMode.HTML
                )
                await q.message.reply_text("✅ Guruhga qidiruv paneli yuborildi!")
            except Exception as e:
                await q.message.reply_text(f"❌ Guruhga yuborib bo'lmadi: {e}")
        else:
            await q.message.reply_text("❌ .env faylida GROUP_ID kiritilmagan!")


# ═══════════════════════════════════════════════════════════════
#  ADMIN: QADAMMA-QADAM KINO QO'SHISH (CONVERSATION)
# ═══════════════════════════════════════════════════════════════

async def add_movie_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin kino qo'shishni boshlaydi (/addmovie yoki tugma)"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        return ConversationHandler.END

    text = (
        "🎬 <b>Yangi kino qo'shish</b>\n\n"
        "1-qadam: <b>Kino nomini</b> kiriting:\n"
        "<i>(Bekor qilish uchun /cancel deb yozing)</i>"
    )
    if update.callback_query:
        await update.callback_query.message.reply_html(text)
    else:
        await update.message.reply_html(text)
    return ADD_TITLE


async def add_movie_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["new_movie"] = {"title": update.message.text.strip()}
    await update.message.reply_html(
        "2-qadam: <b>Botdagi kodini</b> kiriting:\n"
        "Masalan: <code>Kod:237</code> yoki shunchaki <code>237</code>"
    )
    return ADD_CODE


async def add_movie_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code = update.message.text.strip()
    if not code.lower().startswith("kod:"):
        code = f"Kod:{code}"
    ctx.user_data["new_movie"]["bot_code"] = code

    await update.message.reply_html(
        "3-qadam: <b>Yilini</b> kiriting (masalan: <code>2023</code>):\n"
        "<i>(Agar bilmasangiz yoki kiritishni xohlamasangiz <b>-</b> belgisini yuboring)</i>"
    )
    return ADD_YEAR


async def add_movie_year(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    year = int(val) if val.isdigit() else None
    ctx.user_data["new_movie"]["year"] = year

    await update.message.reply_html(
        "4-qadam: <b>Tili / Janrini</b> kiriting (masalan: <code>O'zbek tilida</code>):\n"
        "<i>(O'tkazib yuborish uchun <b>-</b> yuboring)</i>"
    )
    return ADD_GENRE


async def add_movie_genre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    ctx.user_data["new_movie"]["genre"] = None if val == "-" else val

    await update.message.reply_html(
        "5-qadam: <b>Qo'shimcha ma'lumotlar</b> (Sifati, Davlat, Reyting yoki qisqa tavsif):\n"
        "<i>(O'tkazib yuborish uchun <b>-</b> yuboring)</i>"
    )
    return ADD_DESC


async def add_movie_desc(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    ctx.user_data["new_movie"]["description"] = None if val == "-" else val

    await update.message.reply_html(
        "6-qadam (oxirgi): <b>Kanaldagi post ID raqamini</b> kiriting (xabar linkidagi oxirgi raqam):\n"
        "<i>(Masalan: 1872. Agar post IDsini bilmasangiz <b>-</b> yuboring)</i>"
    )
    return ADD_MSG_ID


async def add_movie_finish(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    msg_id = int(val) if val.isdigit() else None
    m_data = ctx.user_data.get("new_movie", {})
    m_data["channel_msg_id"] = msg_id

    # Bazaga qo'shish
    try:
        new_id = add_movie(
            title=m_data["title"],
            bot_code=m_data["bot_code"],
            title_ru=None,
            title_en=None,
            year=m_data.get("year"),
            genre=m_data.get("genre"),
            description=m_data.get("description"),
            channel_msg_id=m_data.get("channel_msg_id")
        )
        await update.message.reply_html(
            f"✅ <b>Kino muvaffaqiyatli saqlandi!</b>\n\n"
            f"🆔 ID: <code>{new_id}</code>\n"
            f"🎬 Nomi: <b>{m_data['title']}</b>\n"
            f"📥 Kodi: <code>{m_data['bot_code']}</code>\n"
            f"📅 Yili: {m_data.get('year') or '-'}\n"
            f"🇺🇿 Tili: {m_data.get('genre') or '-'}"
        )
    except Exception as e:
        await update.message.reply_html(f"❌ Xatolik yuz berdi: {e}")

    ctx.user_data.clear()
    return ConversationHandler.END


async def add_movie_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Kino qo'shish bekor qilindi.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════
#  GURUH VA SHAXSIY CHAT XABARLARI
# ═══════════════════════════════════════════════════════════════

async def on_user_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg  = update.message
    if not msg or not msg.text:
        return

    text = msg.text.strip()
    user = update.effective_user
    chat = update.effective_chat

    if len(text) < 2:
        return

    is_private = (chat.type == "private")

    # Agar guruhda bo'lsa va GROUP_ID sozlangan bo'lsa tekshiramiz
    if not is_private and GROUP_ID:
        gid = str(GROUP_ID).lstrip("@").lower()
        chat_uname = str(getattr(chat, "username", "") or "").lstrip("@").lower()
        chat_match = (
            str(chat.id) == str(GROUP_ID)
            or (chat_uname and chat_uname == gid)
        )
        if not chat_match:
            return

    # ── Instagram linki ──────────────────────────────────────
    if is_instagram(text):
        await _handle_instagram(ctx, msg, text, user, chat)
        return

    # Guruhda bo'lsa, qachon qidirishi kerakligini tekshiramiz:
    if not is_private:
        # 1. Bot yuborgan xabarga Reply (javob) qilib yozilgan bo'lsa
        is_reply_to_bot = False
        if msg.reply_to_message and msg.reply_to_message.from_user:
            is_reply_to_bot = (msg.reply_to_message.from_user.id == ctx.bot.id or msg.reply_to_message.from_user.is_bot)
        
        # 2. Xabar kalit so'z bilan boshlangan bo'lsa (kino, film, /kino, !kino, kod...)
        # Yoki shunchaki raqam bo'lsa (masalan "209" deb yozsa ham qidirsin)
        starts_with_keyword = any(
            text.lower().startswith(word.lower()) or 
            text.lower().startswith(f"/{word.lower()}") or 
            text.lower().startswith(f"!{word.lower()}")
            for word in (TRIGGER_WORDS + ["kod", "kodi"])
        )
        is_pure_code = text.isdigit()

        # Agar na botga reply bo'lsa, na kalit so'z bo'lsa — oddiy suhbat deb e'tiborsiz qoldiramiz!
        if not (is_reply_to_bot or starts_with_keyword or is_pure_code):
            return

    # ── Kino qidirish ──
    await _handle_search(ctx, msg, text, user, chat)


async def _handle_instagram(ctx, msg, text, user, chat):
    try:
        await ctx.bot.send_message(
            ADMIN_ID,
            f"📸 <b>Instagram linki</b>\n\n"
            f"👤 {mention(user)} (<code>{user.id}</code>)\n"
            f"💬 {chat.title or chat.id}\n\n"
            f"🔗 {text}",
            parse_mode=ParseMode.HTML
        )
    except TelegramError as e:
        logger.error(f"Instagram → admin: {e}")
    try:
        await msg.reply_html(
            "📩 <b>Qabul qilindi!</b>\n⏳ Tez orada yuklab beramiz! 🙏",
            disable_web_page_preview=True
        )
    except TelegramError as e:
        logger.error(f"Instagram → user: {e}")


async def _handle_search(ctx, msg, text, user, chat):
    query   = clean_query(text)
    results = search_movie(query)

    if results:
        log_search(user.id, user.username, user.full_name, query, True)
        m = results[0]

        # Tugmalar: Botga o'tish (kod bilan) va Kanalga o'tish
        buttons = []
        
        # 1. Botga o'tish tugmasi (bosganda to'g'ridan-to'g'ri kod bilan bot ochiladi)
        code_clean = re.sub(r"[^\d]", "", m.get("bot_code", ""))
        bot_url = f"https://t.me/{BOT_USERNAME}?start={code_clean}" if code_clean else f"https://t.me/{BOT_USERNAME}"
        buttons.append([InlineKeyboardButton("🤖 Kinoni botdan olish", url=bot_url)])

        # 2. Kanalga o'tish tugmasi (agar kanal xabar ID bo'lsa)
        if m.get("channel_msg_id") and CHANNEL_ID:
            uname = str(CHANNEL_ID).lstrip("@")
            url   = f"https://t.me/{uname}/{m['channel_msg_id']}"
            buttons.append([InlineKeyboardButton("📺 Kanaldagi postni ko'rish", url=url)])

        keyboard = InlineKeyboardMarkup(buttons)

        try:
            await msg.reply_html(
                movie_card(m),
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
        except TelegramError as e:
            logger.error(f"Movie card: {e}")

    else:
        log_search(user.id, user.username, user.full_name, query, False)

        try:
            await msg.reply_html(
                f"🔎 <b>Qidirilmoqda...</b>\n\n"
                f"<b>«{query}»</b> hozircha bazamizda yo'q.\n"
                f"Tez orada yuklab beramiz! ⏳\n\n"
                f"📺 {CHANNEL_ID}",
                disable_web_page_preview=True
            )
        except TelegramError as e:
            logger.error(f"Not found reply: {e}")

        try:
            await ctx.bot.send_message(
                ADMIN_ID,
                f"🚨 <b>Kino topilmadi!</b>\n\n"
                f"👤 {mention(user)} (<code>{user.id}</code>)\n"
                f"💬 {chat.title or chat.id}\n"
                f"🔍 So'rov: <b>«{query}»</b>\n\n"
                f"📝 Asl xabar: <i>{text}</i>\n\n"
                f"⚠️ Kanalga post qiling!",
                parse_mode=ParseMode.HTML
            )
        except TelegramError as e:
            logger.error(f"Not found → admin: {e}")


# ═══════════════════════════════════════════════════════════════
#  KANAL POSTLARI
# ═══════════════════════════════════════════════════════════════

async def on_channel_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    post = update.channel_post
    if not post or not is_our_channel(update.effective_chat):
        return
    text = post.text or post.caption or ""
    if not text:
        return
    
    # Ro'yxat yoki yakka post
    movies_list = parse_post_multiple(text, message_id=post.message_id)
    if not movies_list:
        return

    added_count = 0
    first_title = ""
    for parsed in movies_list:
        if movie_exists_by_code(parsed["bot_code"]):
            continue
        add_movie(**{k: parsed[k] for k in
                     ["title", "bot_code", "title_ru", "title_en",
                      "year", "genre", "description", "channel_msg_id"]})
        added_count += 1
        if not first_title:
            first_title = parsed["title"]

    if added_count > 0:
        try:
            if added_count == 1:
                txt = f"✅ <b>Yangi kino qo'shildi!</b>\n🎬 {first_title}"
            else:
                txt = f"✅ <b>Kanaldan {added_count} ta kino qo'shildi!</b>\nMasalan: {first_title}..."
            await ctx.bot.send_message(ADMIN_ID, txt, parse_mode=ParseMode.HTML)
        except TelegramError:
            pass


# ═══════════════════════════════════════════════════════════════
#  ADMIN BUYRUQLARI
# ═══════════════════════════════════════════════════════════════

async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_chat.type != "private":
        return
    if update.effective_user.id == ADMIN_ID:
        await update.message.reply_html(
            "👑 <b>Admin boshqaruv paneli</b>\n\n"
            "Kerakli bo'limni tanlang yoki buyruqlardan foydalaning:\n"
            "• /admin – Boshqaruv tugmalari\n"
            "• /addmovie – Yangi kino qo'shish\n"
            "• /listmovies – Barcha kinolar\n"
            "• /delmovie &lt;ID&gt; – Kinoni o'chirish\n"
            "• /panel – Guruhga qidiruv tugmasini yuborish\n"
            "• /sync – Kanal postlarini sinxronlash",
            reply_markup=admin_keyboard()
        )
    else:
        await update.message.reply_html(
            f"👋 <b>Salom!</b>\nKino qidirish uchun nomini yozing!\n📺 {CHANNEL_ID}"
        )


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_html(
        "👑 <b>Admin boshqaruv paneli:</b>",
        reply_markup=admin_keyboard()
    )


async def cmd_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    await update.message.reply_html(
        "🎬 <b>Kino qidirish</b>\n\n"
        "Quyidagi tugmani bosing, kino nomini yozing\n"
        "va <b>Jo'natish</b> tugmasini bosing! 👇",
        reply_markup=search_button()
    )


async def cmd_cleansync(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: /cleansync – Bazadagi eski aralashgan kinolarni tozalab, qayta to'g'ri yuklash"""
    if update.effective_user.id != ADMIN_ID:
        return
    client_db = get_client()
    try:
        client_db.table("movies").delete().neq("id", 0).execute()
        await update.message.reply_text("🧹 Bazadagi eski yozuvlar tozalandi! Endi kanaldan faqat haqiqiy kinolar saralanmoqda...")
    except Exception as e:
        await update.message.reply_text(f"Tozalashda xatolik: {e}")
    await cmd_sync(update, ctx)


async def cmd_sync(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    from config import API_ID, API_HASH
    if not API_ID or not API_HASH:
        await update.message.reply_html(
            "❌ API_ID va API_HASH kerak!\nmy.telegram.org/apps dan oling."
        )
        return
    msg = await update.message.reply_html(f"⏳ <b>Sinxronizatsiya...</b>\n📺 {CHANNEL_ID}")
    try:
        from telethon import TelegramClient
        saved = skipped = errors = total = 0
        async with TelegramClient("sync_session", API_ID, API_HASH) as client:
            async for message in client.iter_messages(CHANNEL_ID, reverse=True):
                total += 1
                text = message.text or message.message or ""
                if not text:
                    skipped += 1
                    continue
                movies_list = parse_post_multiple(text, message_id=message.id)
                if not movies_list:
                    skipped += 1
                    continue
                for parsed in movies_list:
                    if movie_exists_by_code(parsed["bot_code"]):
                        skipped += 1
                        continue
                    try:
                        add_movie(**{k: parsed[k] for k in
                                     ["title", "bot_code", "title_ru", "title_en",
                                      "year", "genre", "description", "channel_msg_id"]})
                        saved += 1
                    except Exception as e:
                        errors += 1
                        logger.error(f"#{message.id}: {e}")
                if total % 100 == 0:
                    try:
                        await msg.edit_text(f"⏳ O'qildi: {total} | Saqlandi: {saved}")
                    except Exception:
                        pass
        await msg.edit_text(
            f"✅ <b>Tugadi!</b>\n\n"
            f"📦 O'qildi  : <b>{total}</b>\n"
            f"💾 Saqlandi : <b>{saved}</b>\n"
            f"⏭ O'tkazildi: <b>{skipped}</b>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        await msg.edit_text(f"❌ Xato:\n<code>{e}</code>", parse_mode=ParseMode.HTML)


async def cmd_listmovies(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    movies = get_all_movies()
    if not movies:
        await update.message.reply_text("📭 Bazada kinolar yo'q.")
        return
    text = f"🎬 <b>Jami {len(movies)} ta kino:</b>\n\n"
    for m in movies[:20]:
        yr = f" ({m['year']})" if m.get("year") else ""
        text += f"<code>{m['id']:>4}</code>  {m['title']}{yr}  → <code>{m['bot_code']}</code>\n"
    if len(movies) > 20:
        text += f"\n... va yana {len(movies)-20} ta."
    await update.message.reply_html(text)


async def cmd_delmovie(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    args = ctx.args
    if not args or not args[0].isdigit():
        await update.message.reply_text("Format: /delmovie <ID>")
        return
    deleted = delete_movie(int(args[0]))
    await update.message.reply_text(
        f"✅ #{args[0]} o'chirildi." if deleted else f"❌ Topilmadi."
    )


async def cmd_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    s = get_stats()
    rate = f"{s['found_count']/s['total_searches']*100:.1f}%" if s["total_searches"] else "—"
    await update.message.reply_html(
        f"📊 <b>Statistika</b>\n\n"
        f"🎬 Kinolar: <b>{s['total_movies']}</b>\n"
        f"🔍 Qidiruvlar: <b>{s['total_searches']}</b>\n"
        f"✅ Topildi: <b>{s['found_count']}</b>\n"
        f"❌ Topilmadi: <b>{s['not_found']}</b>\n"
        f"📈 Muvaffaqiyat: <b>{rate}</b>"
    )


async def on_error(update: object, ctx: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Bot xatosi: {ctx.error}", exc_info=ctx.error)


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    logger.info("🤖 Bot ishga tushmoqda...")
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Admin Kino qo'shish ConversationHandler ──────────────
    add_movie_handler = ConversationHandler(
        entry_points=[
            CommandHandler("addmovie", add_movie_start),
            CallbackQueryHandler(add_movie_start, pattern="^admin_add_movie$")
        ],
        states={
            ADD_TITLE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_title)],
            ADD_CODE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_code)],
            ADD_YEAR:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_year)],
            ADD_GENRE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_genre)],
            ADD_DESC:   [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_desc)],
            ADD_MSG_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_movie_finish)],
        },
        fallbacks=[CommandHandler("cancel", add_movie_cancel)],
    )
    app.add_handler(add_movie_handler)

    # ── Buyruqlar ────────────────────────────────────────────
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("admin",      cmd_admin))
    app.add_handler(CommandHandler("panel",      cmd_panel))
    app.add_handler(CommandHandler("sync",       cmd_sync))
    app.add_handler(CommandHandler("cleansync",  cmd_cleansync))
    app.add_handler(CommandHandler("listmovies", cmd_listmovies))
    app.add_handler(CommandHandler("delmovie",   cmd_delmovie))
    app.add_handler(CommandHandler("stats",      cmd_stats))

    # ── Callback tugmalar ────────────────────────────────────
    app.add_handler(CallbackQueryHandler(on_callback_query))

    # ── Kanal postlari ───────────────────────────────────────
    app.add_handler(MessageHandler(
        filters.ChatType.CHANNEL & filters.TEXT,
        on_channel_post
    ))

    # ── Guruh va shaxsiy chat xabarlari (qidiruv va instagram) 
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        on_user_message
    ))

    app.add_error_handler(on_error)

    logger.info("✅ Polling boshlandi.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
