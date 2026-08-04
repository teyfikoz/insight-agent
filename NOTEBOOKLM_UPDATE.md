# InsightAgent v2.0 — NotebookLM Update
**Date:** Aug 3, 2026 | **Commit:** 2843103

## Yeni Özellikler (v2.0)

### 1. Gemini API Fallback
- **Chain:** NIM → Groq → **Gemini** → rule-based
- **Gemini URL:** `generativelanguage.googleapis.com/v1beta/openai/` (OpenAI-compatible)
- **Model:** `gemini-2.0-flash`
- **Setup:** Settings sekmesinden GEMINI_API_KEY girilir → .env'e kaydedilir
- **Avantaj:** Google'ın en son modeli, SSE streaming desteği

### 2. USB Packager
- **Komut:** `make_usb.sh [/path/to/usb]`
- **İçerik:**
  - wheels/ — pip wheel paketleri (offline kurulum)
  - launch.command (Mac) — tıkla ve çalıştır
  - launch.bat (Windows) — tıkla ve çalıştır
- **Gumroad:** InsightAgent USB $29 ürün (henüz oluşturulmadı)

### 3. Settings Page
- **Port:** 7890
- **Endpoint:** `/api/settings`
- **Ayarlanabilir Parametreler:**
  - NVIDIA_NIM_API_KEY
  - GROQ_API_KEY
  - GEMINI_API_KEY
  - Default target
  - Scan interval (monitor mode)

### 4. Monitor Mode
- **Komut:** `python3 main.py --monitor site.com --interval 3600`
- **Özellik:** Periyodik tarama + email/Slack alert
- **Dashboard:** Tüm taramaların geçmişi ve trendleri

### 5. SkillOpt Self-Evolving Training
- **Dosya:** `skillopt_train.py`
- **Çalışma:** ReflACT loop — her tarama sonrası skills/ dokümanları otomatik iyileşir
- **Backend:** Groq openai_compatible + Gemini fallback
- **Özet:** Skill dosyalarınız, Gemini'nin AI feedback'i ile zamanla daha iyi çıktı vermeye başlar

---

## Teknik Detaylar

### Dashboard (FastAPI)
- **URL:** http://localhost:7890
- **Features:**
  - Live scan progress
  - Historical reports
  - Settings management
  - Skill evolution logs

### Gemini Integration
```python
# .env
GEMINI_API_KEY=your_key

# main.py'de otomatik kullanılır
# NIM unavailable → Groq unavailable → Gemini
```

### USB Install Flow
```bash
# USB'deki insight-agent/
./launch.command          # Mac
./launch.bat              # Windows
# → Virtual env setup + dependencies install + scanner başlat
```

---

## Deploy Komutları

### Hetzner 46.62.164.198
```bash
ssh -i ~/.ssh/id_ed25519 root@46.62.164.198 \
  'cd /var/www/insight-agent && git fetch origin && git reset --hard origin/main && \
   source venv/bin/activate && pip install -r requirements.txt -q && \
   systemctl restart insight-agent'
```

### GitHub
- **Repo:** github.com/teyfikoz/insight-agent (PUBLIC)
- **Main branch:** Always production-ready

---

## Gumroad Product
- **URL:** (Henüz oluşturulmadı)
- **Fiyat:** $29 USD
- **İçerik:** USB paketleme (wheels + launcher + 1 month email support)
- **Positioning:** SEO professionals, digital agencies

---

## Test Sonuçları — Aug 3, 2026 (commit 2843103)

| Test | Durum | Detay |
|------|-------|-------|
| `import httpx, feedparser, fastapi, groq` | ✅ | Tüm bağımlılıklar OK |
| `python3 main.py --target robocheckin.com --no-pdf` | ✅ | SEO 89/100, AI=NVIDIA NIM, 472ms load |
| Dashboard `/api/status` | ✅ | 200, version 2.0.0 |
| Dashboard `/api/settings` | ✅ | 200 |
| Dashboard `/api/reports` | ✅ | 200, 3 rapor |
| Dashboard `/api/jobs` | ✅ | 200 |
| `make_usb.sh /tmp/test_usb` | ✅ | 51 wheels, launch.command + launch.bat |

### Düzeltilen Hatalar
- **requirements.txt:** `httpx>=0.24.0` ve `feedparser>=6.0.0` eklendi (kurulu ama pin'lenmemişti)
- **make_usb.sh:** `pip` → `python3 -m pip` (macOS'ta `pip` PATH'te yok, wheels=0 bug'ı düzeldi)
- **make_usb.sh:** `2>/dev/null` → `--quiet` ile değiştirildi (gerçek hatalar görünür oldu)

## Sonraki Adımlar
1. ✅ Gemini API fallback test et (Settings page üzerinden)
2. ✅ USB packager test et (`make_usb.sh /tmp/test_usb`) — **51 wheels OK**
3. ✅ Monitor mode test et (periyodik tarama)
4. ⏳ Gumroad ürün sayfası oluştur ($29, USB delivery)
5. ⏳ SkillOpt eğitim loop'unu production'da çalıştır

---

**Updated:** Aug 3, 2026
**Status:** v2.0 Production Ready
