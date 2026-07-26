# InsightAgent — AI-Powered Website Intelligence

> Bir domain adı gir, dakikalar içinde SEO analizi + yöneticiye sunulabilir aksiyon planı al.
> NVIDIA NIM → Groq → rule-based fallback zinciri. Tamamen lokal çalışır, hiçbir veri dışarı çıkmaz.

[![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Özellikler

| Modül | Ne yapar |
|---|---|
| **WebScanner** | SSL, yük süresi, title/meta, schema, sitemap, robot.txt, Open Graph taraması |
| **SEOAgent** | NIM/Groq ile SEO skoru (0-100), hızlı kazanımlar, keyword önerileri |
| **ActionPlanAgent** | Yönetici özeti + 7 / 30 / 90 günlük aksiyon planı |
| **SkillOpt** | Skill dosyalarını otomatik eğitir → zamanla daha iyi çıktı |
| **Raporlar** | Markdown + PDF olarak kaydeder |

---

## Kurulum

### A — GitHub'dan (önerilen)

```bash
git clone https://github.com/teyfikoz/insight-agent.git
cd insight-agent

# Sanal ortam oluştur
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

# Bağımlılıkları yükle
pip install -r requirements.txt

# (Opsiyonel) SkillOpt eğitim için
pip install skillopt
```

### B — USB Bellekten (offline kullanım)

USB bellekte şu yapı olmalı:

```
USB:/
  insight-agent/          ← bu reponun kopyası
  wheels/                 ← pip wheel'ları (offline kurulum için)
    requirements_wheels/
```

**USB'den kurulum:**
```bash
# USB sürücünüzü bağlayın (örnek: /Volumes/INSIGHT)
cd /Volumes/INSIGHT/insight-agent

python3 -m venv .venv
source .venv/bin/activate

# İnternet olmadan kurulum (wheels klasöründen)
pip install --no-index --find-links=/Volumes/INSIGHT/wheels/requirements_wheels -r requirements.txt

# Çalıştır
python3 main.py --target hedefsite.com --no-pdf
```

**USB için wheel'ları hazırlamak (internete bağlı makinede bir kez):**
```bash
mkdir -p wheels/requirements_wheels
pip download -r requirements.txt -d wheels/requirements_wheels
```

---

## API Anahtarları

InsightAgent üç katmanlı fallback kullanır — en azından bir tanesi yeterli:

```bash
# .env dosyası oluştur (proje kökünde)
NVIDIA_NIM_API_KEY=nvapi-xxx   # Birincil — en iyi kalite
GROQ_API_KEY=gsk_xxx           # İkincil — hızlı ve ücretsiz
# İkisi de yoksa: rule-based fallback (API'siz çalışır)
```

Anahtarları şuradan al:
- NIM: https://integrate.api.nvidia.com (ücretsiz başlangıç kredisi)
- Groq: https://console.groq.com (ücretsiz tier: 14,400 req/gün)

---

## Kullanım

### Temel tarama

```bash
# Markdown raporu
python3 main.py --target robocheckin.com

# PDF + Markdown
python3 main.py --target b2blife.com --output ~/Desktop/raporlar/

# PDF olmadan (fpdf2 kurulu değilse)
python3 main.py --target techsyncanalytica.com --no-pdf

# Hedef keyword'lerle
python3 main.py --target kredimplus.com --keywords "kredi hesaplama, faiz oranı, banka"

# Sadece SEO raporu (hızlı)
python3 main.py --target site.com --report seo
```

### Çıktı örneği

```
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ InsightAgent — robocheckin.com ┃
┗━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┛
SEO Score      89/100   Grade: A
Load Time      312ms    Fast ✓
SSL            287 gün  ✓
Schema         JSON-LD  ✓
Critical Issues 0       None ✓
AI Provider    NVIDIA NIM

Quick Wins:
  → Canonical URL ekle (30 dk)
  → Next.js generateMetadata kullan (1 saat)
  → Meta description kısalt — 160 char (15 dk)
```

---

## SkillOpt — Kendi Kendini Geliştiren Agentlar

InsightAgent, Microsoft'un [SkillOpt](https://github.com/microsoft/SkillOpt) framework'ünü kullanarak
kendi analiz promptlarını zamanla iyileştirir. Model ağırlıkları değişmez; sadece `skills/*.md` dosyaları güncellenir.

### Nasıl çalışır

```
skills/
  seo_auditor.md          ← başlangıç skill belgesi (tohum)
  action_planner.md       ← başlangıç skill belgesi
  seo_auditor/
    best_skill.md         ← SkillOpt'un eğitip optimize ettiği versiyon
                             (bu dosya varsa onu kullanır, yoksa seed'i kullanır)
```

### İlk eğitimi çalıştır

```bash
# Hızlı test (2 epoch, 2 domain, ~5 dk)
python3 skillopt_train.py --skill seo_auditor --epochs 2 --quick

# Tam eğitim (5 epoch, 5 domain, ~20 dk)
python3 skillopt_train.py --skill seo_auditor --epochs 5

# Action planner eğitimi
python3 skillopt_train.py --skill action_planner --epochs 3

# Gecelik oto-evrim (her iki skill'i 2 epoch eğit)
python3 skillopt_train.py --sleep
```

### Gecelik otomatik eğitim (cron)

```bash
# Her gece 02:00'de çalıştır
crontab -e
0 2 * * * cd /path/to/insight-agent && .venv/bin/python skillopt_train.py --sleep >> /tmp/skillopt_sleep.log 2>&1
```

### Eğitim sonucunu görme

```bash
# Hangi skill kullanılıyor?
cat skills/seo_auditor/best_skill.md   # eğitilmiş versiyon

# Eğitim geçmişi
ls skillopt_runs/seo_auditor/          # epoch_01, epoch_02, ...

# Anlık log
tail -f /tmp/skillopt_sleep.log
```

---

## Proje Yapısı

```
insight-agent/
├── main.py                    ← CLI giriş noktası
├── requirements.txt
├── skillopt_train.py          ← SkillOpt eğitim scripti
├── .env                       ← API anahtarları (git'e commit edilmez)
│
├── agents/
│   ├── base_agent.py          ← NIM → Groq → fallback router
│   ├── seo_agent.py           ← SEO analizi
│   ├── action_plan_agent.py   ← Aksiyon planı
│   └── skill_loader.py        ← SkillOpt skill yükleyici
│
├── scanner/
│   └── web_scanner.py         ← HTTP tarayıcı (SSL, meta, schema, perf)
│
├── reporter/
│   ├── markdown_reporter.py   ← .md raporu
│   └── pdf_reporter.py        ← .pdf raporu (fpdf2 gerekli)
│
├── skills/
│   ├── seo_auditor.md         ← SEO skill (tohum)
│   ├── action_planner.md      ← Aksiyon planı skill (tohum)
│   └── seo_auditor/
│       └── best_skill.md      ← Eğitilmiş artifact (otomatik güncellenir)
│
├── reports/                   ← Oluşturulan raporlar
└── skillopt_runs/             ← Eğitim geçmişi (git'e commit edilmez)
```

---

## USB Bellekte Taşıma Rehberi

Tamamen offline çalıştırmak istiyorsanız:

### 1. Hazırlık (internete bağlı makinede)

```bash
# Repoyu klonla
git clone https://github.com/teyfikoz/insight-agent.git

# Wheel'ları indir
cd insight-agent
mkdir -p ../wheels
pip download -r requirements.txt -d ../wheels
pip download skillopt -d ../wheels

# USB'ye kopyala
cp -r insight-agent /Volumes/USB_ADI/
cp -r wheels /Volumes/USB_ADI/
```

### 2. USB'den kurulum (offline makinede)

```bash
cd /Volumes/USB_ADI/insight-agent

python3 -m venv .venv
source .venv/bin/activate

pip install --no-index --find-links=/Volumes/USB_ADI/wheels -r requirements.txt
pip install --no-index --find-links=/Volumes/USB_ADI/wheels skillopt

# .env dosyası oluştur
echo "GROQ_API_KEY=gsk_xxx" > .env

# Çalıştır
python3 main.py --target hedef.com --no-pdf
```

### 3. Raporu al

Raporlar `reports/` klasörüne kaydedilir. USB bellekte taşıyabilirsiniz:

```bash
cp reports/*.md /Volumes/USB_ADI/raporlar/
```

---

## Bağımlılıklar

```
requests          ← HTTP tarama
beautifulsoup4    ← HTML parse
click             ← CLI
rich              ← terminal UI
fpdf2             ← PDF raporlama (opsiyonel)
openai            ← NIM + Groq API istemcisi
skillopt          ← self-evolving skill eğitimi (opsiyonel)
```

---

## Lisans

MIT — Özgürce kullanabilir, değiştirebilir ve dağıtabilirsiniz.

---

*InsightAgent, [TechSyncAnalytica](https://techsyncanalytica.com) portföyünün bir parçasıdır.*
