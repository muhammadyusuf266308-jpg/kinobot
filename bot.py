# ============================================================
#  bot.py  –  Asosiy Telegram bot (Yangilangan versiya)
#  Admin uchun qulay Kino qo'shish paneli bilan
# ============================================================
import logging
import re
import time
import os
import html as html_mod
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    ForceReply, ReplyKeyboardMarkup, KeyboardButton,
    BotCommand, BotCommandScopeChat, BotCommandScopeDefault
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
    get_client, get_random_movie, get_movies_by_genre, get_top_movies,
    get_similar_movies, get_most_searched, is_user_admin, add_new_admin,
    get_all_admins, remove_admin, invalidate_movies_cache
)
from channel_parser import parse_post, parse_post_multiple
import channel_sync
from ai_service import (
    ask_ai_for_movie_title, parse_post_with_ai, ask_ai_recommend,
    ask_ai_admin_assistant, ask_ai_universal
)

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

# ─── Admin Kanalga Post Yaratish holatlari (ConversationHandler) ─
(
    POST_TITLE,
    POST_CODE,
    POST_QUALITY,
    POST_LANG,
    POST_SOURCE,
    POST_MEDIA,
    POST_CONFIRM
) = range(6, 13)

# ─── Yangi Admin Qo'shish holatlari (ConversationHandler) ─────
ADMIN_INPUT = 13


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
        r"\s+borm[ia]\s+kanalda\??$",
        r"\s+kanalda\??$",
        r"\s+kino\s+borm[ia]\??$",
        r"\s+film\s+borm[ia]\??$",
        r"\s+borm[ia]\??$",
        r"\s+kinosi\??$",
        r"\s+filmini?\??$",
        r"\s+seriali?\??$",
        r"\?+$",
        r"\s+o'?sha\s+kinoni?\s+topib\s+ber\??$",
        r"\s+o'?sha\s+kino\s+i\s+topib\s+ber\??$",
        r"\s+kinoni?\s+topib\s+ber\??$",
        r"\s+topib\s+ber\??$",
        r"\s+iltimos\??$",
        r"\s+kino\??$",
        r"\s+film\??$",
    ]
    for _ in range(3):
        for end in endings:
            t = re.sub(end, "", t, flags=re.IGNORECASE).strip()
    return t or text.strip()


def format_multiple_movies(results: list[dict], query: str, ai_suggested_title: str = None) -> tuple[str, InlineKeyboardMarkup]:
    """Bir nechta kino topilganda chiroyli ro'yxat va tugmalar yaratadi"""
    lines = []
    if ai_suggested_title:
        lines.append(f"🤖 <i>AI aniqlagan kino: <b>{ai_suggested_title}</b></i>\n")

    lines.append(f"🔎 <b>«{html_mod.escape(query)}» bo'yicha {len(results)} ta kino topildi:</b>\n")

    buttons = []
    for idx, m in enumerate(results[:6], 1):
        title = m.get("title", "Nomsiz")
        code = m.get("bot_code", "")
        code_clean = re.sub(r"[^\d]", "", code)
        year_str = f" ({m['year']})" if m.get("year") else ""

        lines.append(f"<b>{idx}. 🎬 {title}{year_str}</b>  👉  <code>{code}</code>")

        bot_url = f"https://t.me/{BOT_USERNAME}?start={code_clean}" if code_clean else f"https://t.me/{BOT_USERNAME}"
        btn_text = f"🤖 {idx}. {title[:20]} ({code})"
        row = [InlineKeyboardButton(btn_text, url=bot_url)]

        if m.get("channel_msg_id") and CHANNEL_ID:
            uname = str(CHANNEL_ID).lstrip("@")
            row.append(InlineKeyboardButton("📺 Post", url=f"https://t.me/{uname}/{m['channel_msg_id']}"))

        buttons.append(row)

    lines.append("\n<i>Kinoni botdan olish uchun kerakli tugmani bosing 👇</i>")
    return "\n".join(lines), InlineKeyboardMarkup(buttons)


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
        [InlineKeyboardButton("➕ Yangi kino qo'shish", callback_data="admin_add_movie"),
         InlineKeyboardButton("📝 Kanalga post yaratish", callback_data="admin_create_post")],
        [InlineKeyboardButton("👥 Adminlar ro'yxati", callback_data="admin_list_admins"),
         InlineKeyboardButton("👤 Yangi admin qo'shish", callback_data="admin_add_admin")],
        [InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
         InlineKeyboardButton("📋 Kinolar ro'yxati", callback_data="admin_list")],
        [InlineKeyboardButton("📢 Guruhga qidiruv tugmasini yuborish", callback_data="admin_send_panel")]
    ])


# ─── Janrlar xaritasi ──────────────────────────────────────────
GENRE_MAP = {
    "💥 Jangari":     "jangari",
    "🚀 Fantastika":  "fantastika",
    "😂 Komediya":    "komediya",
    "😱 Dahshat":     "horror",
    "🧸 Multfilm":    "multfilm",
    "💕 Sevgi":       "sevgi",
    "🔪 Triller":     "triller",
    "🏛 Tarix":       "tarix",
    "👨‍👩‍👧 Oilaviy":  "oilaviy",
    "🎭 Drama":       "drama",
}


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    """Foydalanuvchi uchun doimiy pastki menyu tugmalari"""
    return ReplyKeyboardMarkup(
        [
            [KeyboardButton("🎲 Tasodifiy kino"), KeyboardButton("🔥 Top kinolar")],
            [KeyboardButton("🎭 Janrlar bo'yicha"), KeyboardButton("🤖 Kinochi AI")],
        ],
        resize_keyboard=True,
        input_field_placeholder="Kino nomini yozing...",
    )


def genre_inline_keyboard() -> InlineKeyboardMarkup:
    """Janrlar tanlash uchun inline tugmalar"""
    rows = []
    genre_items = list(GENRE_MAP.items())
    for i in range(0, len(genre_items), 2):
        row = []
        for label, _ in genre_items[i:i+2]:
            row.append(InlineKeyboardButton(label, callback_data=f"genre:{label}"))
        rows.append(row)
    return InlineKeyboardMarkup(rows)


def format_similar_movies(similars: list[dict]) -> str:
    """O'xshash kinolar uchun qisqa matn"""
    if not similars:
        return ""
    lines = ["\n\n💡 <b>Sizga yana yoqishi mumkin:</b>"]
    for m in similars[:4]:
        code = m.get("bot_code", "")
        yr = f" ({m['year']})" if m.get("year") else ""
        lines.append(f"  • <b>{m['title']}{yr}</b>  👉  <code>{code}</code>")
    return "\n".join(lines)




# ═══════════════════════════════════════════════════════════════
#  CALLBACK: Tugmalar bosilganda
# ═══════════════════════════════════════════════════════════════

async def on_callback_query(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    data = q.data

    # Janr tugmasi bosilganda
    if data.startswith("genre:"):
        label = data[len("genre:"):]
        keyword = GENRE_MAP.get(label)
        if keyword:
            movies = get_movies_by_genre(keyword)
            if movies:
                lines = [f"🎭 <b>{label} janridagi kinolar:</b>\n"]
                btns = []
                for m in movies[:8]:
                    yr = f" ({m['year']})" if m.get("year") else ""
                    code = m.get("bot_code", "")
                    code_num = re.sub(r"[^\d]", "", code)
                    lines.append(f"🎬 <b>{m['title']}{yr}</b>  👉  <code>{code}</code>")
                    bot_url = f"https://t.me/{BOT_USERNAME}?start={code_num}" if code_num else f"https://t.me/{BOT_USERNAME}"
                    btns.append([InlineKeyboardButton(f"🤖 {m['title'][:25]} ({code})", url=bot_url)])
                btns.append([InlineKeyboardButton("🎭 Boshqa janr", callback_data="show_genres")])
                await q.message.reply_html(
                    "\n".join(lines),
                    reply_markup=InlineKeyboardMarkup(btns),
                    disable_web_page_preview=True
                )
            else:
                await q.message.reply_html(
                    f"😕 <b>{label}</b> janrida hozircha kino topilmadi.\n\n"
                    "Boshqa janr tanlang yoki kino nomini yozing!",
                    reply_markup=genre_inline_keyboard()
                )
        return

    # Janrlar menyusini chiqarish
    if data == "show_genres":
        await q.message.reply_html(
            "🎭 <b>Qaysi janrdagi kinoni ko'rmoqchisiz?</b>\n\nQuyidagi tugmalardan birini tanlang:",
            reply_markup=genre_inline_keyboard()
        )
        return

    # Tasodifiy kino callback
    if data == "random_movie":
        m = get_random_movie()
        if m:
            buttons = []
            code_clean = re.sub(r"[^\d]", "", m.get("bot_code", ""))
            if code_clean:
                bot_url = f"https://t.me/{BOT_USERNAME}?start={code_clean}"
                buttons.append([InlineKeyboardButton("🤖 Kinoni olish", url=bot_url)])
            if m.get("channel_msg_id") and CHANNEL_ID:
                uname = str(CHANNEL_ID).lstrip("@")
                url   = f"https://t.me/{uname}/{m['channel_msg_id']}"
                buttons.append([InlineKeyboardButton("📺 Kanaldagi post", url=url)])
            buttons.append([InlineKeyboardButton("🎲 Boshqa tavsiya", callback_data="random_movie")])
            await q.message.reply_html(
                "🎲 <b>Boshqa tavsiya:</b>\n\n" + movie_card(m),
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
        return

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
    if not is_user_admin(q.from_user.id, ADMIN_ID):
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
    elif data == "admin_list_admins":
        await cmd_admins(update, ctx)
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
    if not is_user_admin(user_id, ADMIN_ID):
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
#  ADMIN: KANALGA POST YARATISH (CONVERSATION)
# ═══════════════════════════════════════════════════════════════

def format_channel_post_text(data: dict) -> str:
    """Kanal uchun chiroyli post matnini shakllantiradi"""
    title = data.get("title", "")
    code = data.get("code", "")
    quality = data.get("quality", "1080p")
    lang = data.get("lang", "O'zbek tilida")
    source = data.get("source")

    lines = [
        f"🎬 <b>Nomi:</b> {title}",
        f"🎙 <b>Tili:</b> {lang}",
        f"💽 <b>Sifati:</b> {quality}",
    ]
    if source:
        lines.append(f"🌐 <b>Manba:</b> {source}")

    lines.extend([
        "",
        f"🆔 <b>Kino kodi:</b> <code>{code}</code>",
        "",
        f"🤖 <b>Botimiz:</b> @{BOT_USERNAME}",
        f"📢 <b>Kanalimiz:</b> {CHANNEL_ID}",
    ])
    return "\n".join(lines)


async def post_create_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin kanalga post yaratishni boshlaydi (/post yoki tugma)"""
    user_id = update.effective_user.id
    if not is_user_admin(user_id, ADMIN_ID):
        return ConversationHandler.END

    ctx.user_data["channel_post"] = {}
    text = (
        "📝 <b>Kanalga post yaratish</b>\n\n"
        "1-qadam: <b>Kino nomini</b> kiriting:\n"
        "<i>(Bekor qilish uchun /cancel deb yozing)</i>"
    )
    if update.callback_query:
        await update.callback_query.message.reply_html(text)
    else:
        await update.message.reply_html(text)
    return POST_TITLE


async def post_create_title(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data["channel_post"]["title"] = update.message.text.strip()
    await update