# ============================================================
#  sync_local.py  –  Kanaldagi barcha kinolarni bazaga yuklash
#  (Kompyuterda 1 marta ishga tushiriladi)
# ============================================================
import asyncio
from config import API_ID, API_HASH, CHANNEL_ID
from database import get_client, add_movie
from channel_parser import parse_post_multiple
from ai_service import parse_post_with_ai
from telethon import TelegramClient

async def main():
    print("="*50)
    print("🎬 KINO BAZASINI YANGILASH VA TOZALASH")
    print("="*50)

    # 1. Bazani tozalash
    client_db = get_client()
    try:
        client_db.table("movies").delete().neq("id", 0).execute()
        print("🧹 Supabase bazasidagi eski ma'lumotlar tozalandi!")
    except Exception as e:
        print(f"Xatolik: {e}")

    print(f"\n📡 @{CHANNEL_ID.lstrip('@')} kanalidan kinolarni saralab olish boshlandi...")

    saved = 0
    skipped = 0
    total = 0

    # Telethon orqali kanal tarixini to'liq o'qish
    async with TelegramClient("local_user_session", API_ID, API_HASH) as client:
        async for message in client.iter_messages(CHANNEL_ID, reverse=True):
            total += 1
            text = message.text or message.message or ""
            if not text:
                continue

            movies_list = parse_post_multiple(text, message_id=message.id)
            if not movies_list:
                # Agar oddiy parser topolmasa, AI dan so'raymiz
                if "kod" in text.lower() or "kodi" in text.lower():
                    movies_list = parse_post_with_ai(text, message_id=message.id)

            if not movies_list:
                skipped += 1
                continue

            for parsed in movies_list:
                try:
                    add_movie(
                        title=parsed["title"],
                        bot_code=parsed["bot_code"],
                        title_ru=parsed["title_ru"],
                        title_en=parsed["title_en"],
                        year=parsed["year"],
                        genre=parsed["genre"],
                        description=parsed["description"],
                        channel_msg_id=parsed["channel_msg_id"]
                    )
                    saved += 1
                    print(f"  ✅ Saqlandi: {parsed['title']}  ->  {parsed['bot_code']}")
                except Exception as e:
                    print(f"  ❌ Xato (#{message.id}): {e}")

    print("\n" + "="*50)
    print(f"🎉 TUGADI!")
    print(f"📦 Jami tekshirilgan postlar: {total}")
    print(f"🎬 Bazaga saqlangan haqiqiy kinolar: {saved}")
    print(f"🚫 O'tkazib yuborilgan reklamalar/e'lonlar: {skipped}")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(main())
