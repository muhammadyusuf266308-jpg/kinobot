# ============================================================
#  bot.py  –  Asosiy Telegram bot (Yangilangan versiya)
#  Admin uchun qulay Kino qo'shish paneli bilan
# ============================================================
import logging
import re
from telegram import (
    Update, InlineKeyboardMarkup, InlineKeyboardButton,
    ForceReply, ReplyKeyboardMarkup, KeyboardButton
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
    get_all_admins, remove_admin
)
from channel_parser import parse_post, parse_post_multiple
from ai_service import (
    ask_ai_for_movie_title, parse_post_with_ai, ask_ai_recommend,
    ask_ai_admin_assistant
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

    lines.append(f"🔎 <b>«{query}» bo'yicha {len(results)} ta kino topildi:</b>\n")

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
    if user_id != ADMIN_ID:
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
    await update.message.reply_html(
        "2-qadam: <b>Kino kodini</b> kiriting:\n"
        "Masalan: <code>245</code> yoki <code>Kod:245</code>"
    )
    return POST_CODE


async def post_create_code(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    code_raw = update.message.text.strip()
    # Faqat raqam qilib yoki toza formatda olamiz
    code_num = re.sub(r"[^\d]", "", code_raw)
    ctx.user_data["channel_post"]["code"] = code_num or code_raw

    await update.message.reply_html(
        "3-qadam: <b>Kino sifatini</b> kiriting:\n"
        "Masalan: <code>1080p</code>, <code>720p HD</code>\n"
        "<i>(Standart 1080p qoldirish uchun <b>-</b> belgisini yuboring)</i>"
    )
    return POST_QUALITY


async def post_create_quality(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    ctx.user_data["channel_post"]["quality"] = "1080p" if val == "-" else val

    await update.message.reply_html(
        "4-qadam: <b>Kino tilini</b> kiriting:\n"
        "<i>(Standart <b>O'zbek tilida</b> qoldirish uchun <b>-</b> belgisini yuboring)</i>"
    )
    return POST_LANG


async def post_create_lang(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    ctx.user_data["channel_post"]["lang"] = "O'zbek tilida" if val == "-" else val

    await update.message.reply_html(
        "5-qadam (oxirgi): <b>Manba</b> (sayt yoki kanal havolasi):\n"
        "<i>(Agar manba qo'shishni istamasangiz <b>-</b> yoki <b>yo'q</b> deb yozing)</i>"
    )
    return POST_SOURCE


async def post_create_source(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    if val.lower() in ["-", "yo'q", "yoq", "none", "no"]:
        ctx.user_data["channel_post"]["source"] = None
    else:
        ctx.user_data["channel_post"]["source"] = val

    await update.message.reply_html(
        "6-qadam (oxirgi): <b>Kino uchun rasm yoki video</b> yuboring:\n\n"
        "🖼 <b>Rasm</b> yoki 🎬 <b>Video</b> yuborishingiz mumkin.\n"
        "<i>(Rasmsiz/videosiz faqat matnli post chiqarish uchun <b>-</b> yoki <b>yo'q</b> deb yozing)</i>"
    )
    return POST_MEDIA


async def post_create_media(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    p_data = ctx.user_data["channel_post"]

    # Rasm, video yoki o'tkazib yuborishni tekshiramiz
    if msg.photo:
        p_data["media_type"] = "photo"
        p_data["media_file_id"] = msg.photo[-1].file_id
    elif msg.video:
        p_data["media_type"] = "video"
        p_data["media_file_id"] = msg.video.file_id
    elif msg.text and msg.text.strip().lower() in ["-", "yo'q", "yoq", "none", "no", "kerakmas"]:
        p_data["media_type"] = None
        p_data["media_file_id"] = None
    else:
        await msg.reply_html(
            "⚠️ Iltimos, kino uchun <b>rasm</b> yoki <b>video</b> yuboring, yoki o'tkazib yuborish uchun <b>-</b> deb yozing:"
        )
        return POST_MEDIA

    preview_text = format_channel_post_text(p_data)

    confirm_keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Kanalga joylash", callback_data="post_send_channel")],
        [InlineKeyboardButton("❌ Bekor qilish", callback_data="post_cancel")]
    ])

    m_type = p_data.get("media_type")
    fid = p_data.get("media_file_id")

    if m_type == "photo" and fid:
        await msg.reply_photo(
            photo=fid,
            caption=f"👀 <b>Post ko'rinishi (Prevyu):</b>\n\n{preview_text}\n\nKanalga joylansinmi?",
            parse_mode=ParseMode.HTML,
            reply_markup=confirm_keyboard
        )
    elif m_type == "video" and fid:
        await msg.reply_video(
            video=fid,
            caption=f"👀 <b>Post ko'rinishi (Prevyu):</b>\n\n{preview_text}\n\nKanalga joylansinmi?",
            parse_mode=ParseMode.HTML,
            reply_markup=confirm_keyboard
        )
    else:
        await msg.reply_html(
            "👀 <b>Post ko'rinishi (Prevyu):</b>\n\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"{preview_text}\n"
            "━━━━━━━━━━━━━━━━━━━━\n\n"
            "Kanalga joylansinmi?",
            reply_markup=confirm_keyboard,
            disable_web_page_preview=True
        )
    return POST_CONFIRM


async def post_create_confirm(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "post_cancel":
        ctx.user_data.clear()
        await q.message.edit_text("❌ Post yaratish bekor qilindi.")
        return ConversationHandler.END

    if q.data == "post_send_channel":
        p_data = ctx.user_data.get("channel_post", {})
        if not p_data:
            await q.message.edit_text("❌ Ma'lumot topilmadi.")
            return ConversationHandler.END

        post_text = format_channel_post_text(p_data)
        m_type = p_data.get("media_type")
        fid = p_data.get("media_file_id")

        try:
            if m_type == "photo" and fid:
                sent_msg = await ctx.bot.send_photo(
                    chat_id=CHANNEL_ID,
                    photo=fid,
                    caption=post_text,
                    parse_mode=ParseMode.HTML
                )
            elif m_type == "video" and fid:
                sent_msg = await ctx.bot.send_video(
                    chat_id=CHANNEL_ID,
                    video=fid,
                    caption=post_text,
                    parse_mode=ParseMode.HTML
                )
            else:
                sent_msg = await ctx.bot.send_message(
                    chat_id=CHANNEL_ID,
                    text=post_text,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

            # Post kanalga chiqdi, endi bot bazasiga ham avtomatik qo'shamiz!
            try:
                code_val = f"Kod:{p_data['code']}"
                add_movie(
                    title=p_data["title"],
                    bot_code=code_val,
                    genre=p_data.get("lang"),
                    description=f"💽 Sifati: {p_data.get('quality')}",
                    channel_msg_id=sent_msg.message_id
                )
            except Exception as e:
                logger.warning(f"Post bazaga saqlashda xato: {e}")

            success_txt = (
                f"✅ <b>Post muvaffaqiyatli kanalga joylandi!</b>\n\n"
                f"📢 Kanal: {CHANNEL_ID}\n"
                f"🆔 Xabar ID: <code>{sent_msg.message_id}</code>\n"
                f"🎬 Kino: <b>{p_data['title']}</b>"
            )
            if q.message.caption:
                await q.message.edit_caption(caption=success_txt, parse_mode=ParseMode.HTML)
            else:
                await q.message.edit_text(text=success_txt, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.error(f"Kanalga post yuborishda xatolik: {e}")
            err_txt = f"❌ Kanalga post yuborib bo'lmadi:\n<code>{e}</code>"
            if q.message.caption:
                await q.message.edit_caption(caption=err_txt, parse_mode=ParseMode.HTML)
            else:
                await q.message.edit_text(text=err_txt, parse_mode=ParseMode.HTML)

        ctx.user_data.clear()
        return ConversationHandler.END


async def post_create_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text("❌ Post yaratish bekor qilindi.")
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════
#  ADMIN: YANGI ADMIN QO'SHISH VA RO'YXAT (CONVERSATION)
# ═══════════════════════════════════════════════════════════════

async def add_admin_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Faqat bosh admin (ADMIN_ID) yangi admin qo'shishi mumkin"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        if update.callback_query:
            await update.callback_query.answer("⛔ Faqat bosh admin yangi admin qo'sha oladi!", show_alert=True)
        else:
            await update.message.reply_text("⛔ Faqat bosh admin yangi admin qo'sha oladi!")
        return ConversationHandler.END

    text = (
        "👤 <b>Yangi admin qo'shish</b>\n\n"
        "Yangi admin bo'ladigan foydalanuvchining <b>Telegram ID raqamini</b> yuboring:\n"
        "<i>(Masalan: <code>123456789</code>. Bekor qilish uchun /cancel deb yozing)</i>"
    )
    if update.callback_query:
        await update.callback_query.message.reply_html(text)
    else:
        await update.message.reply_html(text)
    return ADMIN_INPUT


async def add_admin_process(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    val = update.message.text.strip()
    digits = re.findall(r"\d+", val)
    if not digits:
        await update.message.reply_html("❌ Noto'g'ri ID. Iltimos faqat raqamlardan iborat Telegram ID kiriting:")
        return ADMIN_INPUT

    new_admin_id = int(digits[0])
    if new_admin_id == ADMIN_ID:
        await update.message.reply_html("ℹ️ Siz allaqachon bosh adminsiz.")
        return ConversationHandler.END

    success = add_new_admin(
        user_id=new_admin_id,
        added_by=update.effective_user.id
    )
    if success:
        await update.message.reply_html(
            f"✅ <b>Yangi admin muvaffaqiyatli qo'shildi!</b>\n\n"
            f"👤 Admin ID: <code>{new_admin_id}</code>\n"
            f"Endi bu foydalanuvchi botning barcha admin funksiyalaridan foydalana oladi."
        )
    else:
        await update.message.reply_html("❌ Adminni qo'shishda xatolik yuz berdi.")
    return ConversationHandler.END


async def add_admin_cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Yangi admin qo'shish bekor qilindi.")
    return ConversationHandler.END


async def cmd_admins(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Adminlar ro'yxatini ko'rish"""
    user_id = update.effective_user.id
    if not is_user_admin(user_id, ADMIN_ID):
        return

    admins = get_all_admins()
    lines = [
        "👥 <b>Bot Adminlari Ro'yxati:</b>\n",
        f"👑 <b>Bosh admin:</b> <code>{ADMIN_ID}</code>"
    ]
    if admins:
        lines.append("\n<b>Qo'shimcha adminlar:</b>")
        for idx, a in enumerate(admins, 1):
            uid = a.get("user_id")
            uname = f" (@{a['username']})" if a.get("username") else ""
            lines.append(f"{idx}. <code>{uid}</code>{uname}")
    else:
        lines.append("\n<i>Hozircha qo'shimcha adminlar yo'q.</i>")

    lines.append("\n💡 <i>Adminni o'chirish: /deladmin &lt;ID&gt;</i>")
    await update.effective_message.reply_html("\n".join(lines))


async def cmd_deladmin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Adminni o'chirish (/deladmin <ID>)"""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        await update.message.reply_text("⛔ Faqat bosh admin boshqa adminlarni o'chira oladi!")
        return

    args = ctx.args
    if not args or not args[0].isdigit():
        await update.message.reply_html("Ishlatish: <code>/deladmin 123456789</code>")
        return

    target_id = int(args[0])
    if target_id == ADMIN_ID:
        await update.message.reply_text("❌ Bosh adminni o'chirib bo'lmaydi!")
        return

    remove_admin(target_id)
    await update.message.reply_html(f"✅ Admin (<code>{target_id}</code>) o'chirildi.")




# ═══════════════════════════════════════════════════════════════
#  GURUH VA SHAXSIY CHAT XABARLARI
# ═══════════════════════════════════════════════════════════════

def is_channel_comment_or_discussion(msg) -> tuple[bool, str]:
    """Foydalanuvchi kanaldagi post ostiga komment (Reply) yozganligini aniqlaydi"""
    if not msg or not msg.reply_to_message:
        return False, ""
    parent = msg.reply_to_message
    is_fwd = getattr(parent, "is_automatic_forward", False)
    is_ch_sender = bool(parent.sender_chat and parent.sender_chat.type == "channel")
    is_ch_fwd = bool(parent.forward_from_chat and parent.forward_from_chat.type == "channel")

    if is_fwd or is_ch_sender or is_ch_fwd:
        context_text = parent.text or parent.caption or ""
        return True, context_text
    return False, ""


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
    is_ch_comment, post_ctx = is_channel_comment_or_discussion(msg)

    # Agar oddiy guruhda bo'lsa (kanal posti ostidagi komment bo'lmasa) va GROUP_ID sozlangan bo'lsa tekshiramiz
    if not is_private and not is_ch_comment and GROUP_ID:
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

    # ── Doimiy menyu tugmalari ────────────────────────────────
    t_lower = text.strip().lower()
    if text == "🎲 Tasodifiy kino":
        await cmd_random(update, ctx)
        return
    if text == "🔥 Top kinolar":
        await cmd_top(update, ctx)
        return
    if text == "🎭 Janrlar bo'yicha":
        await cmd_genre(update, ctx)
        return
    if text == "🤖 Kinochi AI":
        await cmd_ai(update, ctx)
        return

    # ── 1. KANAL POSTIGA KOMMENT (REPLY) YOZILGANDA ──────────
    if is_ch_comment:
        query_c = clean_query(text)
        # Avval bazadan qidirib ko'ramiz
        results_c = search_movie(query_c)
        if results_c:
            m = results_c[0]
            code_clean = re.sub(r"[^\d]", "", m.get("bot_code", ""))
            bot_url = f"https://t.me/{BOT_USERNAME}?start={code_clean}" if code_clean else f"https://t.me/{BOT_USERNAME}"
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Kinoni botdan olish", url=bot_url)]])
            await msg.reply_html(
                f"🎬 <b>{m['title']}</b>\n"
                f"Kino kodi: <code>{m.get('bot_code')}</code>\n\n"
                f"Kinoni quyidagi havola orqali botdan yuklab olishingiz mumkin 👇",
                reply_markup=btn,
                disable_web_page_preview=True
            )
            return

        # Agar bazada bo'lmasa, kino so'rovi ekanligini AI orqali tekshiramiz
        ai_data_c = ask_ai_for_movie_title(text)
        if ai_data_c and isinstance(ai_data_c, dict) and (ai_data_c.get("title_uz") or ai_data_c.get("title_en")):
            ai_res, _ = _search_ai_title(ai_data_c)
            if ai_res:
                m = ai_res[0]
                code_clean = re.sub(r"[^\d]", "", m.get("bot_code", ""))
                bot_url = f"https://t.me/{BOT_USERNAME}?start={code_clean}" if code_clean else f"https://t.me/{BOT_USERNAME}"
                btn = InlineKeyboardMarkup([[InlineKeyboardButton("🤖 Kinoni botdan olish", url=bot_url)]])
                await msg.reply_html(
                    f"🎬 <b>{m['title']}</b>\n"
                    f"Kino kodi: <code>{m.get('bot_code')}</code>\n\n"
                    f"Kinoni quyidagi havola orqali botdan yuklab olishingiz mumkin 👇",
                    reply_markup=btn,
                    disable_web_page_preview=True
                )
                return

            tit = ai_data_c.get("title_uz") or ai_data_c.get("title_en")
            yr = f" ({ai_data_c['year']})" if ai_data_c.get("year") else ""
            await msg.reply_html(
                f"🤖 <b>AI aniqlagan kino:</b> <b>{tit}</b>{yr}\n\n"
                f"⏳ <b>Biroz kuting!</b> Ushbu kino hozircha kanalimizda mavjud emas. "
                f"Adminga so'rovingiz yetkazildi, tez orada kanalga yuklab beriladi!",
                disable_web_page_preview=True
            )
            try:
                await ctx.bot.send_message(
                    ADMIN_ID,
                    f"🚨 <b>Kanal kommentidan yangi kino so'rovi!</b>\n\n"
                    f"👤 {mention(user)} (<code>{user.id}</code>)\n"
                    f"🎬 AI aniqlagan: <b>{tit}</b>{yr}\n"
                    f"💬 Komment yozilgan post: <i>{post_ctx[:120]}</i>\n"
                    f"📝 Foydalanuvchi kommenti: <i>{text}</i>\n\n"
                    f"⚠️ Kanalga yuklab, /post qiling!",
                    parse_mode=ParseMode.HTML
                )
            except TelegramError as e:
                logger.error(f"Komment alert admin error: {e}")
            return

        # Agar kino so'rovi bo'lmasa — post ostidagi savol yoki fikrga admin nomidan AI javob beradi
        ans = ask_ai_admin_assistant(
            text, user_name=user.first_name, chat_title=chat.title,
            is_channel_comment=True, post_context=post_ctx
        )
        if ans:
            await msg.reply_html(ans, disable_web_page_preview=True)
        return

    # ── AI kayfiyat/tavsiya (masalan "kulgili kino tavsiya ber") ──
    MOOD_KEYWORDS = [
        "tavsiya", "qanday kino", "nima ko'ray", "nima ko'rsam", "kayfiyat",
        "qaysi kino", "bir kino", "qiziq kino", "yaxshi kino", "zo'r kino",
        "komediya ayt", "dahshat kino", "sevgi kino", "jangari ayt",
        "tavsiya ber", "tavsiya qil",
    ]
    is_mood_request = any(kw in t_lower for kw in MOOD_KEYWORDS)
    if is_mood_request and not any(text.lower().startswith(w) for w in ["kinochi", "/kinochi"]):
        try:
            ai_rec = ask_ai_recommend(text)
            if ai_rec and ai_rec.get("genre_keyword"):
                gk = ai_rec["genre_keyword"]
                reason = ai_rec.get("reason", "")
                movies = get_movies_by_genre(gk, limit=6)
                if movies:
                    lines = [
                        f"🤖 <b>AI tavsiyasi:</b> {reason}\n",
                        f"🎭 <b>{gk.capitalize()} janridan</b> sizga mos kinolar:\n"
                    ]
                    btns = []
                    for mv in movies[:6]:
                        yr = f" ({mv['year']})" if mv.get("year") else ""
                        code = mv.get("bot_code", "")
                        code_num = re.sub(r"[^\d]", "", code)
                        lines.append(f"🎬 <b>{mv['title']}{yr}</b>  👉  <code>{code}</code>")
                        if code_num:
                            bot_url = f"https://t.me/{BOT_USERNAME}?start={code_num}"
                            btns.append([InlineKeyboardButton(f"▶️ {mv['title'][:30]}", url=bot_url)])
                    btns.append([InlineKeyboardButton("🎭 Boshqa janr tanlash", callback_data="show_genres")])
                    await msg.reply_html(
                        "\n".join(lines),
                        reply_markup=InlineKeyboardMarkup(btns),
                        disable_web_page_preview=True
                    )
                    return
        except Exception as e:
            logger.warning(f"AI mood tavsiya xatosi: {e}")

    # ── "kinochi ..." bilan boshlangan xabarlar (to'g'ridan-to'g'ri AI orqali kino topish) ──
    is_kinochi = any(
        text.lower().startswith(w) for w in ["kinochi", "/kinochi", "!kinochi"]
    )

    # Guruhda bo'lsa, qachon javob berishini tekshiramiz:
    is_reply_to_bot = False
    if not is_private and msg.reply_to_message and msg.reply_to_message.from_user:
        is_reply_to_bot = (msg.reply_to_message.from_user.id == ctx.bot.id or msg.reply_to_message.from_user.is_bot)

    starts_with_keyword = any(
        text.lower().startswith(word.lower()) or 
        text.lower().startswith(f"/{word.lower()}") or 
        text.lower().startswith(f"!{word.lower()}")
        for word in (TRIGGER_WORDS + ["kod", "kodi", "ai", "qidir", "admin"])
    )
    is_pure_code = text.strip().isdigit()
    is_bot_mentioned = bool(ctx.bot.username and f"@{ctx.bot.username.lower()}" in text.lower())

    is_explicit = bool(is_kinochi or is_reply_to_bot or starts_with_keyword or is_pure_code or is_bot_mentioned)

    # Guruhda begona suhbatlarga bot aralashmaydi
    if not is_private and not is_explicit:
        return

    # ── Muloqot, salom-alik yoki umumiy savollar (Admin nomidan AI javobi) ──
    CONVERSATIONAL_KEYWORDS = [
        "salom", "assalom", "qalaysiz", "qalesiz", "yaxshimisiz", "tuzukmisiz",
        "admin", "kim bu", "qanday ishlaydi", "ishlatish", "yordam", "rahmat",
        "raxmat", "spasibo", "nima qila olasan", "kod nima", "qayerdan", "topolmadim",
        "tushunmadim", "qanday qidiraman", "bot haqida"
    ]
    is_chat_msg = any(kw in t_lower for kw in CONVERSATIONAL_KEYWORDS)
    if (is_chat_msg or text.startswith("?")) and not is_kinochi and not is_pure_code:
        direct_movie = search_movie(clean_query(text))
        if direct_movie and words_score(clean_query(text), direct_movie[0]["title"]) >= 0.8:
            pass
        else:
            ans = ask_ai_admin_assistant(text, user_name=user.first_name, chat_title=chat.title)
            if ans:
                await msg.reply_html(ans, disable_web_page_preview=True)
                return

    # ── Kino qidirish ──
    await _handle_search(ctx, msg, text, user, chat, is_explicit=is_explicit, is_kinochi=is_kinochi)


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


def _search_ai_title(ai_result: dict | str) -> tuple[list[dict], str | None]:
    """AI qaytargan ma'lumotlar (o'zbekcha, inglizcha, ruscha nomlar va muqobillar) bo'yicha bazadan qidiradi"""
    if not ai_result:
        return [], None

    if isinstance(ai_result, str):
        candidates = [ai_result]
        display_title = ai_result
    elif isinstance(ai_result, dict):
        display_title = ai_result.get("title_uz") or ai_result.get("title_en") or ai_result.get("title_ru")
        candidates = []
        for key in ["title_uz", "title_en", "title_ru"]:
            val = ai_result.get(key)
            if val and val not in candidates:
                candidates.append(val)
        for alt in ai_result.get("alt_titles", []):
            if alt and alt not in candidates:
                candidates.append(alt)
    else:
        return [], None

    # Har bir nom variantini tekshiramiz
    for cand in candidates:
        res = search_movie(cand)
        if res:
            return res, cand

        # Sarlavhadagi ajratkichlar (masalan: "Titanik / Titanic" yoki "(yoki ...)")
        variants = [p.strip(' ()"\'') for p in re.split(r'\(yoki|\byoki\b|\bor\b|/|\)', cand) if len(p.strip(' ()"\'')) >= 3]
        for v in variants:
            res_v = search_movie(v)
            if res_v:
                return res_v, v

    return [], display_title


async def _handle_search(ctx, msg, text, user, chat, is_explicit: bool = True, is_kinochi: bool = False):
    query = clean_query(text)
    results = []
    ai_suggested_title = None
    ai_data = None

    if is_kinochi:
        # 1. Foydalanuvchi "kinochi ..." deb yozganda: TO'G'RIDAN-TO'G'RI AI ga yuboramiz!
        try:
            ai_data = ask_ai_for_movie_title(query)
            if ai_data:
                results, ai_suggested_title = _search_ai_title(ai_data)
        except Exception as e:
            logger.warning(f"AI kinochi qidiruv xatosi: {e}")
    else:
        # 2. Oddiy so'rovda ("kino tor", "qasoskorlar"...): AVVAL BAZADAN QIDIRILADI!
        results = search_movie(query)

        # Agar bazada TOPILMASA, faqat shundagina AI ga murojaat qilinadi!
        if not results and len(query) >= 4 and is_explicit:
            try:
                ai_data = ask_ai_for_movie_title(query)
                if ai_data:
                    results, ai_suggested_title = _search_ai_title(ai_data)
            except Exception as e:
                logger.warning(f"AI qidiruv xatosi: {e}")

    if results:
        log_search(user.id, user.username, user.full_name, query, True)

        # Agar 1 ta kino topilsa — to'liq kartochka chiqaramiz
        if len(results) == 1:
            m = results[0]
            buttons = []
            code_clean = re.sub(r"[^\d]", "", m.get("bot_code", ""))
            bot_url = f"https://t.me/{BOT_USERNAME}?start={code_clean}" if code_clean else f"https://t.me/{BOT_USERNAME}"
            buttons.append([InlineKeyboardButton("🤖 Kinoni botdan olish", url=bot_url)])

            if m.get("channel_msg_id") and CHANNEL_ID:
                uname = str(CHANNEL_ID).lstrip("@")
                url = f"https://t.me/{uname}/{m['channel_msg_id']}"
                buttons.append([InlineKeyboardButton("📺 Kanaldagi postni ko'rish", url=url)])

            keyboard = InlineKeyboardMarkup(buttons)
            reply_text = movie_card(m)
            if ai_suggested_title:
                reply_text = f"🤖 <i>AI aniqlagan kino: <b>{ai_suggested_title}</b></i>\n\n" + reply_text

            # O'xshash kinolar qo'shamiz
            try:
                similars = get_similar_movies(
                    movie_id=m.get("id", 0),
                    genre=m.get("genre"),
                    title=m.get("title"),
                    limit=4
                )
                if similars:
                    reply_text += format_similar_movies(similars)
            except Exception:
                pass

        else:
            # Agar bir nechta kino topilsa — barchasini tugmali ro'yxat qilib chiqaramiz!
            reply_text, keyboard = format_multiple_movies(results, query, ai_suggested_title)

        try:
            await msg.reply_html(
                reply_text,
                reply_markup=keyboard,
                disable_web_page_preview=True
            )
        except TelegramError as e:
            logger.error(f"Movie card: {e}")

    elif is_explicit:
        log_search(user.id, user.username, user.full_name, query, False)

        # Agar AI kinoni aniqlagan bo'lsa (lekin u bazada hali bo'lmasa)
        if ai_data and isinstance(ai_data, dict) and (ai_data.get("title_uz") or ai_data.get("title_en")):
            tit = ai_data.get("title_uz") or ai_data.get("title_en")
            yr = f" ({ai_data['year']})" if ai_data.get("year") else ""
            en_extra = f" (<i>{ai_data['title_en']}</i>)" if ai_data.get("title_en") and ai_data["title_en"].lower() != tit.lower() else ""

            user_msg = (
                f"🤖 <b>AI aniqlagan kino:</b> <b>{tit}</b>{en_extra}{yr}\n\n"
                f"📌 <i>Ushbu kino hozircha kanalimiz va bazamizda mavjud emas.</i>\n"
                f"⏳ <b>Biroz kuting!</b> Adminga so'rovingiz yetkazildi, tez orada kanalga yuklab beriladi!\n\n"
                f"📺 Kanalimiz: {CHANNEL_ID}"
            )
            try:
                await msg.reply_html(user_msg, disable_web_page_preview=True)
            except TelegramError as e:
                logger.error(f"AI identified not found reply: {e}")

            try:
                await ctx.bot.send_message(
                    ADMIN_ID,
                    f"🚨 <b>Kino so'rovi (Bazada yo'q)!</b>\n\n"
                    f"👤 {mention(user)} (<code>{user.id}</code>)\n"
                    f"💬 {chat.title or chat.id}\n"
                    f"🎬 AI aniqlagan: <b>{tit}</b>{yr}\n"
                    f"🔍 Foydalanuvchi so'rovi: <b>«{query}»</b>\n"
                    f"📝 Asl xabar: <i>{text}</i>\n\n"
                    f"⚠️ Kanalga yuklab, /post orqali chiqaring!",
                    parse_mode=ParseMode.HTML
                )
            except TelegramError as e:
                logger.error(f"AI identified → admin: {e}")
        else:
            # Agar AI kinoni aniqlay olmagan bo'lsa — admin nomidan umumiy javob bera oladimi tekshiramiz
            ans = ask_ai_admin_assistant(text, user_name=user.first_name, chat_title=chat.title)
            if ans and len(text.split()) > 2:
                try:
                    await msg.reply_html(ans, disable_web_page_preview=True)
                except TelegramError as e:
                    logger.error(f"Admin assistant reply: {e}")
            else:
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
        try:
            movies_list = parse_post_with_ai(text, message_id=post.message_id)
        except Exception as e:
            logger.warning(f"AI post tahlil xatosi: {e}")

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
    args = ctx.args
    # /start <code> — kino kodi bilan kelgan bo'lsa, to'g'ridan-to'g'ri kino yuboramiz
    if args and args[0].isdigit():
        code_num = args[0]
        results = search_movie(code_num)
        if results:
            m = results[0]
            buttons = []
            code_clean = re.sub(r"[^\d]", "", m.get("bot_code", ""))
            bot_url = f"https://t.me/{BOT_USERNAME}?start={code_clean}"
            buttons.append([InlineKeyboardButton("🤖 Kinoni botdan olish", url=bot_url)])
            if m.get("channel_msg_id") and CHANNEL_ID:
                uname = str(CHANNEL_ID).lstrip("@")
                url   = f"https://t.me/{uname}/{m['channel_msg_id']}"
                buttons.append([InlineKeyboardButton("📺 Kanaldagi postni ko'rish", url=url)])
            await update.message.reply_html(
                movie_card(m),
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True
            )
            return

    if is_user_admin(update.effective_user.id, ADMIN_ID):
        await update.message.reply_html(
            "👑 <b>Admin boshqaruv paneli</b>\n\n"
            "Kerakli bo'limni tanlang yoki buyruqlardan foydalaning:\n"
            "• /admin – Boshqaruv tugmalari\n"
            "• /post – Kanalga yangi post yaratish\n"
            "• /admins – Adminlar ro'yxati\n"
            "• /addadmin – Yangi admin qo'shish\n"
            "• /deladmin &lt;ID&gt; – Adminni o'chirish\n"
            "• /addmovie – Yangi kino qo'shish\n"
            "• /listmovies – Barcha kinolar\n"
            "• /delmovie &lt;ID&gt; – Kinoni o'chirish\n"
            "• /panel – Guruhga qidiruv tugmasini yuborish\n"
            "• /sync – Kanal postlarini sinxronlash",
            reply_markup=admin_keyboard()
        )
    else:
        await update.message.reply_html(
            f"👋 <b>Salom, {update.effective_user.first_name}!</b>\n\n"
            "🎬 Kino nomi yoki kodini yozing va men topib beraman!\n\n"
            "📺 Kanal: <b>@UzKinoMoviie</b>\n\n"
            "👇 Quyidagi tugmalardan ham foydalanishingiz mumkin:",
            reply_markup=main_menu_keyboard()
        )


async def cmd_admin(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id, ADMIN_ID):
        return
    await update.message.reply_html(
        "👑 <b>Admin boshqaruv paneli:</b>",
        reply_markup=admin_keyboard()
    )


async def cmd_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id, ADMIN_ID):
        return
    await update.message.reply_html(
        "🎬 <b>Kino qidirish</b>\n\n"
        "Quyidagi tugmani bosing, kino nomini yozing\n"
        "va <b>Jo'natish</b> tugmasini bosing! 👇",
        reply_markup=search_button()
    )


async def cmd_cleansync(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Admin: /cleansync – Bazani tozalash"""
    if update.effective_user.id != ADMIN_ID:
        return
    client_db = get_client()
    try:
        client_db.table("movies").delete().neq("id", 0).execute()
        await update.message.reply_html(
            "🧹 <b>Bazadagi eski ma'lumotlar tozalandi!</b>\n\n"
            "Telegram xavfsizlik qoidasi sababli botlar kanal tarixini to'liq o'qiy olmaydi.\n"
            "Kanal tarixidagi eski postlarni 1 marta bazaga yuklash uchun kompyuteringizda:\n"
            "<code>cd D:\\kino-bot-prod</code>\n"
            "<code>python sync_local.py</code>\n"
            "buyrug'ini bering. Yangi kanal postlari esa avtomatik bazaga tushaveradi!"
        )
    except Exception as e:
        await update.message.reply_text(f"Xatolik: {e}")


async def cmd_sync(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id, ADMIN_ID):
        return
    msg = await update.message.reply_html("🔄 <b>Kanal va baza holati tekshirilmoqda...</b>")
    try:
        movies = get_all_movies()
        total_count = len(movies)
        latest = movies[:5]
        latest_text = ""
        for idx, m in enumerate(latest, 1):
            latest_text += f"  {idx}. 🎬 <b>{m['title']}</b>  👉  <code>{m['bot_code']}</code>\n"

        status_text = (
            f"✅ <b>Kanal va Baza holati tekshirildi!</b>\n\n"
            f"📢 <b>Kanal:</b> {CHANNEL_ID}\n"
            f"🎬 <b>Bazada saqlangan jami kinolar:</b> <b>{total_count} ta</b>\n"
            f"⚡ <b>Avtomatik post qabul qilish:</b> 🟢 <b>FAOL</b>\n\n"
            f"🆕 <b>Oxirgi saqlangan kinolar:</b>\n{latest_text}\n"
            f"💡 <i>Kanalga yangi kino posti tashlansa, bot uni avtomatik qabul qilib bazaga qo'shadi!</i>"
        )
        await msg.edit_text(status_text, parse_mode=ParseMode.HTML)
    except Exception as e:
        await msg.edit_text(f"❌ Xatolik yuz berdi: {e}")


async def cmd_listmovies(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_user_admin(update.effective_user.id, ADMIN_ID):
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
    if not is_user_admin(update.effective_user.id, ADMIN_ID):
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
    if not is_user_admin(update.effective_user.id, ADMIN_ID):
        return
    s = get_stats()
    rate = f"{s['found_count']/s['total_searches']*100:.1f}%" if s["total_searches"] else "—"
    top_q = get_most_searched(5)
    top_text = ""
    for i, item in enumerate(top_q, 1):
        top_text += f"  {i}. <code>{item['query']}</code> — <b>{item['count']}x</b>\n"
    await update.message.reply_html(
        f"📊 <b>Statistika</b>\n\n"
        f"🎬 Kinolar: <b>{s['total_movies']}</b>\n"
        f"🔍 Qidiruvlar: <b>{s['total_searches']}</b>\n"
        f"✅ Topildi: <b>{s['found_count']}</b>\n"
        f"❌ Topilmadi: <b>{s['not_found']}</b>\n"
        f"📈 Muvaffaqiyat: <b>{rate}</b>\n\n"
        f"🔥 <b>Eng ko'p qidirilganlar:</b>\n{top_text or '  — ma\'lumot yo\'q'}"
    )


async def cmd_top(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Top kinolar: /top yoki 🔥 Top kinolar tugmasi"""
    movies = get_top_movies(10)
    if not movies:
        await update.message.reply_html("😕 Hozircha bazada kinolar yo'q.")
        return
    lines = ["🔥 <b>Eng so'nggi qo'shilgan kinolar:</b>\n"]
    btns = []
    for i, m in enumerate(movies, 1):
        yr = f" ({m['year']})" if m.get("year") else ""
        code = m.get("bot_code", "")
        code_num = re.sub(r"[^\d]", "", code)
        lines.append(f"{i}. 🎬 <b>{m['title']}{yr}</b>  👉  <code>{code}</code>")
        if code_num:
            bot_url = f"https://t.me/{BOT_USERNAME}?start={code_num}"
            btns.append([InlineKeyboardButton(f"▶️ {i}. {m['title'][:28]}", url=bot_url)])
    await update.message.reply_html(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(btns) if btns else None,
        disable_web_page_preview=True
    )


async def cmd_random(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Tasodifiy kino tavsiyasi: /random yoki 🎲 Tasodifiy kino tugmasi"""
    m = get_random_movie()
    if not m:
        await update.message.reply_html("😕 Hozircha bazada kinolar yo'q.")
        return
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
    await update.message.reply_html(
        "🎲 <b>Bugun sizga tavsiya:</b>\n\n" + movie_card(m),
        reply_markup=InlineKeyboardMarkup(buttons),
        disable_web_page_preview=True
    )


async def cmd_genre(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Janrlar menyusi: /genre yoki 🎭 Janrlar bo'yicha tugmasi"""
    await update.message.reply_html(
        "🎭 <b>Qaysi janrdagi kinoni ko'rmoqchisiz?</b>\n\n"
        "Quyidagi tugmalardan birini tanlang:",
        reply_markup=genre_inline_keyboard()
    )


async def cmd_ai(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    """Kinochi AI yordamida kino topish: /ai yoki 🤖 Kinochi AI tugmasi"""
    await update.message.reply_html(
        "🤖 <b>Kinochi AI</b>\n\n"
        "Quyidagicha yozib yuboring:\n"
        "• <i>kinochi: o'rgimchak odam haqida kino</i>\n"
        "• <i>kinochi: kulgili kino tavsiya ber</i>\n"
        "• <i>kinochi: 2023 yilgi jangari kino</i>\n\n"
        "Yoki shunchaki <b>kinochi</b> so'zidan boshlang! 👇"
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

    # ── Admin Kanalga Post Yaratish ConversationHandler ──────
    create_post_handler = ConversationHandler(
        entry_points=[
            CommandHandler("post", post_create_start),
            CallbackQueryHandler(post_create_start, pattern="^admin_create_post$")
        ],
        states={
            POST_TITLE:   [MessageHandler(filters.TEXT & ~filters.COMMAND, post_create_title)],
            POST_CODE:    [MessageHandler(filters.TEXT & ~filters.COMMAND, post_create_code)],
            POST_QUALITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, post_create_quality)],
            POST_LANG:    [MessageHandler(filters.TEXT & ~filters.COMMAND, post_create_lang)],
            POST_SOURCE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, post_create_source)],
            POST_MEDIA:   [MessageHandler(filters.PHOTO | filters.VIDEO | (filters.TEXT & ~filters.COMMAND), post_create_media)],
            POST_CONFIRM: [CallbackQueryHandler(post_create_confirm, pattern="^post_")],
        },
        fallbacks=[
            CommandHandler("cancel", post_create_cancel),
            CallbackQueryHandler(post_create_confirm, pattern="^post_cancel$")
        ],
    )
    app.add_handler(create_post_handler)

    # ── Yangi Admin Qo'shish ConversationHandler ─────────────
    add_admin_handler = ConversationHandler(
        entry_points=[
            CommandHandler("addadmin", add_admin_start),
            CallbackQueryHandler(add_admin_start, pattern="^admin_add_admin$")
        ],
        states={
            ADMIN_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_admin_process)],
        },
        fallbacks=[CommandHandler("cancel", add_admin_cancel)],
    )
    app.add_handler(add_admin_handler)

    # ── Buyruqlar ────────────────────────────────────────────
    app.add_handler(CommandHandler("start",      cmd_start))
    app.add_handler(CommandHandler("post",       post_create_start))
    app.add_handler(CommandHandler("admins",     cmd_admins))
    app.add_handler(CommandHandler("addadmin",   add_admin_start))
    app.add_handler(CommandHandler("deladmin",   cmd_deladmin))
    app.add_handler(CommandHandler("admin",      cmd_admin))
    app.add_handler(CommandHandler("panel",      cmd_panel))
    app.add_handler(CommandHandler("sync",       cmd_sync))
    app.add_handler(CommandHandler("cleansync",  cmd_cleansync))
    app.add_handler(CommandHandler("listmovies", cmd_listmovies))
    app.add_handler(CommandHandler("delmovie",   cmd_delmovie))
    app.add_handler(CommandHandler("stats",      cmd_stats))
    app.add_handler(CommandHandler("top",        cmd_top))
    app.add_handler(CommandHandler("random",     cmd_random))
    app.add_handler(CommandHandler("genre",      cmd_genre))
    app.add_handler(CommandHandler("ai",         cmd_ai))

    # ── Callback tugmalar ────────────────────────────────────
    app.add_handler(CallbackQueryHandler(on_callback_query))

    # ── Kanal postlari (matnli va rasmli/videoli postlar) ──
    app.add_handler(MessageHandler(
        filters.ChatType.CHANNEL & (filters.TEXT | filters.CAPTION),
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
