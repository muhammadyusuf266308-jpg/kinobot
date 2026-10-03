# 🎬 KinoBot - Telegram Kino Qidiruv Boti

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Telegram Bot](https://img.shields.io/badge/Telegram-Bot-blue?logo=telegram)](https://telegram.org/)

**KinoBot** — bu Telegram orqali ishlaydigan zamonaviy kino qidiruv va tavsiya boti. Foydalanuvchilar kino nomini, kodini yoki hatto syujetini yozib, bir zumda kerakli kinoni topishlari mumkin. Bot Google Gemini AI yordamida syujetlar bo'yicha intellektual qidiruv hamda kino tavsiyalari beradi.

---

## ✨ Asosiy funksiyalar

### 🔍 Kino qidirish
- **Kod bo'yicha**: `Kod:123` formatida kino qidirish
- **Nom bo'yicha**: Kino nomini yozib qidirish
- **Syujet bo'yicha**: AI yordamida kino tavsifini yozib topish
- **Inline qidiruv**: `@bot_username kino_nomi` orqali istalgan chatda qidirish

### 🤖 AI yordamchisi
- Google Gemini AI integratsiyasi
- Syujet bo'yicha intellektual kino aniqlash
- Kayfiyat va janr bo'yicha kino tavsiyasi
- Ko'p tilli qo'llab-quvvatlash (O'zbek, Rus, Ingliz)

### 📊 Kanal integratsiyasi
- Telegram kanal postlarini avtomatik parsing
- Ko'p kinoli ro'yxatlarni aniqlash
- Telethon orqali kanal tarixini o'qish
- Yangi postlarni avtomatik indekslashtirish

### 👨‍💼 Admin panel
- Statistika ko'rish
- Kino qo'shish/tahrirlash/o'chirish
- Foydalanuvchilar boshqaruvi
- Kanal sinxronizatsiyasi

---

## 🚀 O'rnatish

### Talablar
- Python 3.9 yoki yuqori
- Telegram Bot Token
- Supabase account
- Google Gemini API key (ixtiyoriy, AI funksiyalar uchun)
- Telegram API credentials (kanal parsing uchun)

### 1. Repository ni klonlash
```bash
git clone https://github.com/muhammadyusuf266308-jpg/kinobot.git
cd kinobot
```

### 2. Virtual environment yaratish
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 3. Dependency larni o'rnatish
```bash
pip install -r requirements.txt
```

### 4. Environment sozlash
`.env.example` faylini `.env` ga nusxalash va to'ldirish:
```bash
cp .env.example .env
```

`.env` faylini tahrirlash:
```env
# Telegram Bot
BOT_TOKEN=your_bot_token_from_@BotFather
ADMIN_ID=your_telegram_user_id
CHANNEL_ID=@your_channel_username
GROUP_ID=@your_group_username

# Telethon (kanal parsing uchun)
API_ID=your_api_id_from_my.telegram.org
API_HASH=your_api_hash

# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your_service_role_key

# Google Gemini AI (ixtiyoriy)
GEMINI_API_KEY=your_gemini_api_key
```

### 5. Database yaratish
Supabase dashboard orqali `supabase_schema.sql` faylini import qiling:
```bash
# Yoki Supabase CLI orqali
supabase db push
```

### 6. Botni ishga tushirish
```bash
python bot.py
```

---

## 📁 Loyiha strukturasi

```
kinobot/
├── bot.py                 # Asosiy bot mantiqiy
├── ai_service.py          # Google Gemini AI integratsiyasi
├── database.py            # Supabase database operatsiyalari
├── channel_parser.py      # Kanal post parsing
├── config.py              # Konfiguratsiya va sozlamalar
├── sync_local.py          # Lokal database sinxronizatsiya
├── requirements.txt       # Python dependencies
├── supabase_schema.sql    # Database schema
├── Procfile              # Railway/Heroku deploy
├── railway.toml          # Railway konfiguratsiya
├── .env.example          # Environment o'zgaruvchilar namunasi
├── .gitignore            # Git ignore qoidalari
└── webapp/               # Web interface (ixtiyoriy)
```

---

## 🔧 Foydalanish

### Bot buyruqlari

| Buyruq | Tavsif |
|--------|--------|
| `/start` | Botni ishga tushirish va asosiy menyu |
| `/search` | Kino qidirish |
| `/recommend` | Kino tavsiyasi olish |
| `/stats` | Statistika (faqat admin) |
| `/sync` | Kanal sinxronizatsiyasi (faqat admin) |
| `/add` | Yangi kino qo'shish (faqat admin) |

### Qidiruv usullari

**1. Kod bo'yicha:**
```
Kod:123
kod: 456
```

**2. Nom bo'yicha:**
```
Spider-Man
Terminator
```

**3. Syujet bo'yicha:**
```
O'rgimchak inson kiyingan yigit Nyu-Yorkda jinoyatchilarga qarshi kurashadi
```

**4. Inline qidiruv:**
```
@your_bot_username Spider-Man
```

---

## 🛠 Development

### Test muhiti
```bash
# Development dependencies o'rnatish
pip install -r requirements-dev.txt

# Testlarni ishga tushirish
pytest tests/

# Code linting
flake8 .
black .
mypy .
```

### Database migratsiya
```bash
# Yangi migratsiya yaratish
supabase migration new migration_name

# Migratsiyalarni qo'llash
supabase db push
```

---

## 🚢 Deploy

### Railway.app
1. [Railway](https://railway.app) ga kirish
2. "New Project" → "Deploy from GitHub"
3. Repository ni tanlash
4. Environment variables ni sozlash
5. Deploy!

Railway avtomatik `railway.toml` va `Procfile` dan foydalanadi.

### Heroku
```bash
heroku login
heroku create your-bot-name
heroku config:set BOT_TOKEN=your_token
# Boshqa environment variables ni qo'shish
git push heroku main
```

### VPS/Server
```bash
# Systemd service yaratish
sudo nano /etc/systemd/system/kinobot.service

# Service konfiguratsiyasi:
[Unit]
Description=KinoBot Telegram Bot
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/kinobot
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python bot.py
Restart=always

[Install]
WantedBy=multi-user.target

# Service ni yoqish
sudo systemctl enable kinobot
sudo systemctl start kinobot
```

---

## 🤝 Hissa qo'shish

Loyihaga hissa qo'shmoqchimisiz? Ajoyib! [CONTRIBUTING.md](CONTRIBUTING.md) faylini o'qing.

1. Repository ni fork qiling
2. Feature branch yarating (`git checkout -b feature/amazing-feature`)
3. O'zgarishlarni commit qiling (`git commit -m 'feat: add amazing feature'`)
4. Branch ni push qiling (`git push origin feature/amazing-feature`)
5. Pull Request oching

---

## 📄 Litsenziya

Bu loyiha MIT litsenziyasi ostida tarqatiladi. Batafsil ma'lumot uchun [LICENSE](LICENSE) faylini ko'ring.

---

## 📞 Aloqa

**Muallif**: Muhammad Yusuf  
**GitHub**: [@muhammadyusuf266308-jpg](https://github.com/muhammadyusuf266308-jpg)

---

## 🙏 Minnatdorchilik

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot) - Telegram Bot API
- [Supabase](https://supabase.com/) - Backend & Database
- [Google Gemini](https://deepmind.google/technologies/gemini/) - AI xizmatlari
- [Telethon](https://github.com/LonamiWebs/Telethon) - Telegram MTProto API

---

## ⭐ Star History

Agar loyiha yoqsa, star bosing! ⭐

---

**Made with ❤️ in Uzbekistan**
