"""
Test channel_parser.py module

Tests for movie post parsing functionality
"""
import pytest
from channel_parser import (
    parse_post,
    parse_post_multiple,
    _clean_emojis,
    _clean_title_candidate
)


class TestCleanFunctions:
    """Test utility cleaning functions"""
    
    def test_clean_emojis(self):
        """Test emoji removal"""
        assert _clean_emojis("🎬 Kino nomi") == "Kino nomi"
        assert _clean_emojis("📽 Film 🎥") == "Film"
        assert _clean_emojis("Oddiy matn") == "Oddiy matn"
    
    def test_clean_title_candidate(self):
        """Test title cleaning"""
        # Qo'shtirnoq ichidagi nom
        assert _clean_title_candidate('"Spider-Man"') == "Spider-Man"
        
        # Ortiqcha so'zlarni tozalash
        text = "Terminator filmi Full HD skachat"
        cleaned = _clean_title_candidate(text)
        assert "Full HD" not in cleaned
        assert "skachat" not in cleaned
        
        # Yil va til
        text = "Avatar Uzbek tilida 2022"
        cleaned = _clean_title_candidate(text)
        assert "Uzbek tilida" not in cleaned


class TestSingleMovieParsing:
    """Test single movie post parsing"""
    
    def test_parse_simple_kod_format(self):
        """Test parsing 'Kod:123' format"""
        text = """
🎬 Kino nomi: Spider-Man
📅 Yili: 2022
🆔 Kodi: 123
"""
        result = parse_post(text, message_id=1)
        
        assert result is not None
        assert result["title"] == "Spider-Man"
        assert result["year"] == 2022
        assert result["bot_code"] == "Kod:123"
        assert result["channel_msg_id"] == 1
    
    def test_parse_kod_variations(self):
        """Test different kod formats"""
        # "Kod:456"
        assert parse_post("Film\nKod:456", 1)["bot_code"] == "Kod:456"
        
        # "kodi: 789"
        assert parse_post("Film\nkodi: 789", 1)["bot_code"] == "Kod:789"
        
        # "Film kodi; 111"
        assert parse_post("Film kodi; 111", 1)["bot_code"] == "Kod:111"
    
    def test_parse_no_kod_returns_none(self):
        """Test that posts without kod return None"""
        text = "Bu oddiy post, kod yo'q"
        assert parse_post(text) is None
    
    def test_parse_spam_returns_none(self):
        """Test spam/ads are ignored"""
        text = "Kanal sotiladi, arzonga! Kod:123"
        assert parse_post(text) is None
    
    def test_parse_complex_post(self):
        """Test complex post with multiple fields"""
        text = """
🎬 Kino nomi: "Terminator 2"
📅 Yili: 1991
🎙 Til: O'zbek | Rus
🎭 Janr: Fantastika, Jangari
💽 Sifat: Full HD
🌍 Davlat: AQSH
⭐ IMDB: 8.6
🆔 Film kodi: 999
"""
        result = parse_post(text, message_id=100)
        
        assert result is not None
        assert "Terminator 2" in result["title"]
        assert result["year"] == 1991
        assert result["bot_code"] == "Kod:999"
        assert result["genre"] is not None
        assert result["description"] is not None


class TestMultipleMovieParsing:
    """Test multiple movies in one post"""
    
    def test_parse_movie_list(self):
        """Test parsing list of movies"""
        text = """
127 — 📺Tor
126 — 📺Temir Odam
125 — 📺Qasoskorlar
"""
        results = parse_post_multiple(text, message_id=50)
        
        assert len(results) >= 2
        assert any("Tor" in r["title"] for r in results)
        assert any("Temir Odam" in r["title"] for r in results)
        
        # Check codes
        codes = [r["bot_code"] for r in results]
        assert "Kod:127" in codes
        assert "Kod:126" in codes
    
    def test_parse_numbered_list(self):
        """Test numbered format '№124. Movie'"""
        text = """
№147 - Momaqaldiroqlar
№146 - Qora dul
№145 - Ajdar
"""
        results = parse_post_multiple(text, message_id=60)
        
        assert len(results) >= 2
        assert all(r["bot_code"].startswith("Kod:") for r in results)
    
    def test_parse_single_movie_as_list(self):
        """Test single movie returns list with one item"""
        text = """
🎬 Nomi: Spider-Man
Kodi: 555
"""
        results = parse_post_multiple(text, message_id=70)
        
        assert len(results) == 1
        assert results[0]["title"] == "Spider-Man"
        assert results[0]["bot_code"] == "Kod:555"


class TestEdgeCases:
    """Test edge cases and error handling"""
    
    def test_empty_text(self):
        """Test empty or too short text"""
        assert parse_post("") is None
        assert parse_post("abc") is None
        assert parse_post_multiple("") == []
    
    def test_title_with_year_in_name(self):
        """Test extracting year from title"""
        text = "Avatar 2 (2022)\nKodi: 777"
        result = parse_post(text)
        
        assert result is not None
        assert result["year"] == 2022
    
    def test_ignore_bot_links(self):
        """Test ignoring bot/channel mentions"""
        text = """
Kino: Avatar
Kodi: 888
@kinolar_bot orqali
"""
        result = parse_post(text)
        
        assert result is not None
        assert "@kinolar_bot" not in result["title"]
    
    def test_quoted_title_extraction(self):
        """Test extracting title from quotes"""
        text = '''
Yangi kino: "Sherlok Xolms"
Film kodi: 333
'''
        result = parse_post(text)
        
        assert result is not None
        assert "Sherlok Xolms" in result["title"]


# Pytest fixtures
@pytest.fixture
def sample_movie_post():
    """Sample movie post for testing"""
    return """
🎬 Kino nomi: Inception
📅 Yili: 2010
🎙 Til: O'zbek
🎭 Janr: Fantastika
💽 Sifat: Full HD
⭐ IMDB: 8.8
🆔 Kod: 1001
"""


@pytest.fixture
def sample_movie_list():
    """Sample movie list for testing"""
    return """
501 — Avatar
502 — Titanic
503 — Interstellar
"""


def test_with_fixture(sample_movie_post):
    """Test using fixture"""
    result = parse_post(sample_movie_post)
    assert result is not None
    assert result["title"] == "Inception"
    assert result["year"] == 2010


if __name__ == "__main__":
    # Run tests
    pytest.main([__file__, "-v"])



class TestPostFormats:
    """Kanaldagi haqiqiy post turlari"""

    def test_arrow_format_keeps_season(self):
        text = ("🎬 ➺ Lutsifer\n🎞 ➺ 1-Fasl\n🇺🇿 ➺ O'zbek Tilida\n🌍 ➺ AQSH filmi\n"
                "⚔️ ➺ Jangari, fantastika\n\n♻️ Kino kodi: 182\n\nBizning bot:@UzKinoMov1eBot")
        r = parse_post_multiple(text, 1)
        assert len(r) == 1
        assert r[0]["title"] == "Lutsifer 1-Fasl"
        assert r[0]["bot_code"] == "Kod:182"

    def test_plain_title_with_code(self):
        r = parse_post_multiple("Yetti qirollik ritsari\n\nKino kodi: 170\n\n📢 Botimiz:\n@UzKinoMov1eBot", 2)
        assert [(x["title"], x["bot_code"]) for x in r] == [("Yetti qirollik ritsari", "Kod:170")]

    def test_list_with_wrapped_titles(self):
        text = "RO'YXAT\n\n136 — 🟥 Deadpool\n135 — 🟥 Shang-Chi: O'nta\nUzuk Afsonasi\n134 — 🟥 QORA BEVA\n\nBotga kerakli kodni tashlang"
        r = parse_post_multiple(text, 3)
        titles = {x["bot_code"]: x["title"] for x in r}
        assert titles["Kod:135"] == "Shang-Chi: O'nta Uzuk Afsonasi"
        assert titles["Kod:134"] == "QORA BEVA"

    def test_channel_link_list(self):
        text = ("Chuqur 👇\n\n(@chuqur_serial_uzbek_t1lida)\n\n"
                "Shelbylar oilasi | Thomas Shelby 👇\n\n(@shelbylar_oilas1)")
        r = parse_post_multiple(text, 4)
        codes = {x["bot_code"]: x for x in r}
        assert "Link:chuqur_serial_uzbek_t1lida" in codes
        assert codes["Link:shelbylar_oilas1"]["title"] == "Shelbylar oilasi"
        assert codes["Link:shelbylar_oilas1"]["title_en"] == "Thomas Shelby"

    def test_code_only_post(self):
        r = parse_post_multiple("Kino kodi: 215\n\n📢 Botimiz: @UzKinoMov1eBot", 5)
        assert r[0]["bot_code"] == "Kod:215"
        assert r[0]["title"] == "Kino #215"

    def test_code_only_uses_media_filename(self):
        r = parse_post_multiple("Kino kodi: 99", 6, media_name="Yetti_qirollik_ritsari_720p.mp4")
        assert r[0]["title"] == "Yetti qirollik ritsari"

    def test_name_only_media_post(self):
        r = parse_post_multiple("Oppenheimer", 7, has_media=True)
        assert r[0]["bot_code"] == "Post:7"
        assert r[0]["title"] == "Oppenheimer"

    def test_name_only_requires_media_and_rejects_ads(self):
        assert parse_post_multiple("Oppenheimer", 8) == []
        assert parse_post_multiple("Obuna bo'ling, konkurs!", 9, has_media=True) == []