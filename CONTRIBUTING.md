# 🤝 KinoBot loyihasiga hissa qo'shish

Birinchi navbatda, loyihaga qiziqish bildirganingiz uchun rahmat! KinoBot jamoasiga xush kelibsiz! 🎉

## 📋 Mundarija

- [Kodeks](#kodeks)
- [Qanday hissa qo'shish mumkin](#qanday-hissa-qoshish-mumkin)
- [Development sozlash](#development-sozlash)
- [Pull Request jarayoni](#pull-request-jarayoni)
- [Kod standartlari](#kod-standartlari)
- [Commit xabarlari](#commit-xabarlari)
- [Test yozish](#test-yozish)

---

## 📜 Kodeks

### Bizning va'damiz

Ochiq va xushmuomala muhitni yaratish uchun biz hamma uchun yoqimli tajriba yaratishga intilamiz.

### Bizning standartlarimiz

**Ijobiy xatti-harakatlar:**
- ✅ Hurmatli va samimiy muloqot
- ✅ Turli fikrlarni hurmat qilish
- ✅ Konstruktiv tanqid qabul qilish
- ✅ Jamoa manfaatlariga e'tibor

**Qabul qilinmaydigan xatti-harakatlar:**
- ❌ Haqoratli yoki kamsituvchi iboralar
- ❌ Trolling yoki provokatsiya
- ❌ Shaxsiy ma'lumotlarni ruxsatsiz e'lon qilish
- ❌ Professional bo'lmagan xatti-harakatlar

---

## 🚀 Qanday hissa qo'shish mumkin

### Bug xabar qilish

Xatolik topganingizda, issue oching va quyidagilarni yozing:
1. **Qisqa tavsif** - Xatolik nima?
2. **Qayta takrorlash bosqichlari** - Qanday yuzaga keladi?
3. **Kutilgan natija** - Nima bo'lishi kerak edi?
4. **Haqiqiy natija** - Nima bo'ldi?
5. **Muhit** - Python versiyasi, OS, va h.k.
6. **Ekran rasmlari** - Agar mumkin bo'lsa

**Shablon:**
```markdown
**Tavsif:**
Bot kod bo'yicha qidiruvda xatolik beradi

**Qayta takrorlash:**
1. Botga /start yuboring
2. "Kod:123" yozing
3. Xatolik yuzaga keladi

**Kutilgan:** Kino topilishi kerak
**Haqiqiy:** "Database error" xabari

**Muhit:**
- Python: 3.9.5
- OS: Ubuntu 22.04
- Bot version: 1.0.0
```

### Yangi funksiya taklif qilish

Yangi fikr bor? Issue oching:
1. **Funksiya tavsifi** - Nima qo'shmoqchisiz?
2. **Muammo** - Qaysi muammoni hal qiladi?
3. **Yechim** - Qanday ishlashi kerak?
4. **Alternativalar** - Boshqa yo'llar bormi?

---

## 🛠 Development sozlash

### 1. Repository ni fork qilish
```bash
# GitHub da "Fork" tugmasini bosing
# Fork qilingan repo ni klonlash
git clone https://github.com/YOUR_USERNAME/kinobot.git
cd kinobot
```

### 2. Upstream qo'shish
```bash
git remote add upstream https://github.com/muhammadyusuf266308-jpg/kinobot.git
```

### 3. Virtual environment
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

### 4. Dependencies
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

### 5. Pre-commit hooks
```bash
pre-commit install
```

### 6. Environment sozlash
```bash
cp .env.example .env
# .env faylini to'ldiring
```

---

## 🔄 Pull Request jarayoni

### 1. Yangi branch yaratish
```bash
git checkout -b feature/amazing-feature
# yoki
git checkout -b fix/bug-description
```

**Branch naming:**
- `feature/` - Yangi funksiya
- `fix/` - Bug fix
- `docs/` - Hujjatlar
- `refactor/` - Code refactoring
- `test/` - Test qo'shish
- `chore/` - Kichik o'zgarishlar

### 2. O'zgarishlar qilish
```bash
# Kod yozish
# Testlar yozish
# Hujjatlarni yangilash
```

### 3. Code quality tekshirish
```bash
# Format check
black .
isort .

# Linting
flake8 .
pylint bot.py ai_service.py database.py

# Type checking
mypy .

# Tests
pytest tests/ -v --cov
```

### 4. Commit qilish
```bash
git add .
git commit -m "feat: add amazing feature"
```

### 5. Push va PR
```bash
git push origin feature/amazing-feature
# GitHub da Pull Request oching
```

### 6. PR tavsifi

**Yaxshi PR tavsifi:**
```markdown
## O'zgarishlar
- Yangi kino tavsiya algoritmi qo'shildi
- AI javob formati yaxshilandi

## Muammo
Closes #123

## Test qilingan
- [x] Unit testlar
- [x] Integration testlar
- [x] Manual test (local)

## Screenshots
[Agar kerak bo'lsa]

## Checklist
- [x] Code formatted (black, isort)
- [x] Linting passed (flake8, pylint)
- [x] Type hints added (mypy)
- [x] Tests written
- [x] Documentation updated
```

---

## 📏 Kod standartlari

### Python Style Guide

**PEP 8 standartiga amal qilish:**
```python
# ✅ Yaxshi
def calculate_movie_score(rating: float, votes: int) -> float:
    """Calculate weighted movie score.
    
    Args:
        rating: Movie rating (0-10)
        votes: Number of votes
        
    Returns:
        Weighted score
    """
    if votes < 100:
        return rating * 0.5
    return rating


# ❌ Yomon
def calc(r,v):
    if v<100:return r*0.5
    return r
```

### Type Hints
```python
# ✅ Har doim type hints ishlating
from typing import Optional, List, Dict

async def search_movies(
    query: str,
    limit: int = 10
) -> List[Dict[str, any]]:
    """Search movies by query."""
    pass


# ❌ Type hints yo'q
async def search_movies(query, limit=10):
    pass
```

### Docstrings
```python
# ✅ Google style docstring
def parse_movie_code(text: str) -> Optional[str]:
    """Extract movie code from text.
    
    Supports multiple formats:
    - "Kod:123"
    - "kodi: 456"
    - "<<789>>"
    
    Args:
        text: Input text to parse
        
    Returns:
        Movie code if found, None otherwise
        
    Example:
        >>> parse_movie_code("Kod:123")
        "123"
    """
    pass
```

### Error Handling
```python
# ✅ Aniq exception handling
try:
    movie = await db.get_movie(code)
except DatabaseConnectionError as e:
    logger.error(f"DB connection failed: {e}")
    raise
except MovieNotFoundError:
    logger.warning(f"Movie {code} not found")
    return None


# ❌ Umumiy exception
try:
    movie = await db.get_movie(code)
except Exception:
    pass
```

### Logging
```python
import logging

logger = logging.getLogger(__name__)

# ✅ To'g'ri logging
logger.info(f"Processing movie search: {query}")
logger.warning(f"Rate limit approaching: {rate}/min")
logger.error(f"AI service failed: {error}", exc_info=True)

# ❌ Print statements
print("Processing search...")  # Faqat debug uchun
```

---

## 💬 Commit xabarlari

**Conventional Commits formatidan foydalaning:**

```
<type>(<scope>): <subject>

<body>

<footer>
```

### Types:
- `feat` - Yangi funksiya
- `fix` - Bug fix
- `docs` - Hujjatlar
- `style` - Format (code logic o'zgarmagan)
- `refactor` - Code refactoring
- `perf` - Performance yaxshilash
- `test` - Test qo'shish
- `chore` - Build, CI, dependencies

### Misollar:
```bash
# Yangi funksiya
git commit -m "feat(ai): add plot-based movie search"

# Bug fix
git commit -m "fix(database): handle connection timeout"

# Documentation
git commit -m "docs(readme): update installation steps"

# Refactoring
git commit -m "refactor(parser): simplify code extraction logic"

# Breaking change
git commit -m "feat(api)!: change search endpoint response format

BREAKING CHANGE: search API now returns array of objects instead of IDs"
```

---

## 🧪 Test yozish

### Unit Tests
```python
# tests/test_parser.py
import pytest
from channel_parser import parse_movie_code


def test_parse_standard_code():
    """Test standard 'Kod:123' format"""
    assert parse_movie_code("Kod:123") == "123"


def test_parse_case_insensitive():
    """Test case insensitive parsing"""
    assert parse_movie_code("kod:456") == "456"
    assert parse_movie_code("KODI: 789") == "789"


def test_parse_no_code():
    """Test when no code present"""
    assert parse_movie_code("Random text") is None


@pytest.mark.asyncio
async def test_ai_movie_search():
    """Test AI movie search"""
    from ai_service import ask_ai_for_movie_title
    
    result = await ask_ai_for_movie_title(
        "O'rgimchak odam kinosi"
    )
    
    assert result is not None
    assert "title_uz" in result
```

### Test Coverage
```bash
# Minimum 80% coverage talab qilinadi
pytest tests/ --cov=. --cov-report=html --cov-report=term
```

---

## 🎯 Ustunlik joylari

### Yaxshi birinchi issue'lar

Quyidagi label'lar yaxshi boshlang'ich:
- `good first issue` - Yangi contributorlar uchun
- `help wanted` - Yordam kerak
- `documentation` - Hujjatlar
- `enhancement` - Kichik yaxshilanishlar

### Texnik yordam kerak bo'lgan joylar:
1. **Test coverage** oshirish
2. **Type hints** qo'shish
3. **Documentation** yaxshilash
4. **Performance** optimization
5. **Error handling** kuchaytirish

---

## 📞 Savol-javob

### Qayerda savol berish mumkin?

1. **GitHub Discussions** - Umumiy savollar
2. **Issues** - Bug va feature request
3. **Pull Request comments** - Code review
4. **Direct contact** - Maxfiy masalalar uchun

### Review jarayoni

PR'ingiz quyidagi bosqichlardan o'tadi:
1. ✅ Automated checks (CI/CD)
2. ✅ Code review (maintainer)
3. ✅ Test coverage check
4. ✅ Documentation check
5. ✅ Approval va merge

---

## 🏆 Contributors

Barcha contributor'lar README.md da e'lon qilinadi!

---

## 📄 Litsenziya

Loyihaga hissa qo'shish orqali siz o'z kodingizni [MIT License](LICENSE) ostida taqdim etishga rozilik bildirasiz.

---

**Yana bir bor rahmat! Sizning hissangiz loyihani yaxshilashga yordam beradi! 🚀**
