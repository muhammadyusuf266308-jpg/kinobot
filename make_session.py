# ============================================================
# make_session.py – TG_SESSION matnini BIR MARTA yaratish (kompyuterda)
#   python make_session.py
# Chiqqan uzun matnni hosting (Railway) o'zgaruvchilariga TG_SESSION nomi bilan qo'ying.
# DIQQAT: bu matn Telegram akkauntingizga kirish kaliti — hech kimga bermang, GitHub ga yuklamang!
# ============================================================
from telethon.sessions import StringSession
from telethon.sync import TelegramClient

from config import API_HASH, API_ID

with TelegramClient(StringSession(), API_ID, API_HASH) as client:
    print("\nTG_SESSION=" + client.session.save())