# راهنمای نصب و راه‌اندازی (فارسی) — Intelligence Workspace

این راهنما قدم‌به‌قدم می‌گوید چطور همین پروژه (Open WebUI + فضای «اطلاعات و تحلیل» با سه حالت
**کارشناس موضوع**، **اطلاعات پروازهای Elasticsearch** و **تحلیل فایل**) را روی سیستم خودت — به‌صورت
**کاملاً آفلاین** — نصب و اجرا کنی.

هر دستور را دقیقاً به همان ترتیبی که نوشته شده اجرا کن. دستورها برای **Linux / macOS** نوشته شده‌اند و
تفاوت‌های **Windows** در انتهای هر بخش آمده است.

---

## فهرست

0. [پیش‌نیازها](#۰-پیشنیازها)
1. [دریافت کد](#۱-دریافت-کد)
2. [نصب بک‌اند (Python)](#۲-نصب-بکاند-python)
3. [نصب فرانت‌اند (Node)](#۳-نصب-فرانتاند-node)
4. [فایل تنظیمات `.env`](#۴-فایل-تنظیمات-env)
5. [اجرا — روش الف: حالت توسعه (توصیه‌شده)](#۵-اجرا--روش-الف-حالت-توسعه-توصیهشده)
6. [اجرا — روش ب: تک‌پورت / شبیه Production](#۶-اجرا--روش-ب-تکپورت--شبیه-production)
7. [اولین ورود و ساخت حساب مدیر](#۷-اولین-ورود-و-ساخت-حساب-مدیر)
8. [اتصال مدل هوش مصنوعی محلی](#۸-اتصال-مدل-هوش-مصنوعی-محلی)
9. [اتصال Elasticsearch](#۹-اتصال-elasticsearch)
10. [تغییر «موضوع X»](#۱۰-تغییر-موضوع-x)
11. [بررسی سلامت](#۱۱-بررسی-سلامت)
12. [عیب‌یابی](#۱۲-عیبیابی)

---

## ۰. پیش‌نیازها

| مورد | حداقل | پیشنهاد |
| --- | --- | --- |
| Python | 3.10 | **3.11** |
| Node.js | 20 | **20 یا 22** |
| RAM | 4 GB (حالت توسعه) | **8 GB+** (برای `npm run build`) |
| فضای دیسک | 3 GB | 6 GB |
| مدل محلی | Ollama یا هر سرور سازگار با OpenAI | `llama3.1:8b` |
| Elasticsearch | نسخه 8 یا 9 (اختیاری — بدون آن حالت دمو فعال است) | — |

بررسی نسخه‌ها:

```bash
python3 -V      # باید 3.10 یا بالاتر باشد
node -v         # باید v20 یا بالاتر باشد
npm -v
git --version
```

> **Windows:** Python و Node را از سایت رسمی نصب کن و در هنگام نصب Python گزینه
> «Add python.exe to PATH» را تیک بزن. دستورها را در **PowerShell** اجرا کن.

---

## ۱. دریافت کد

```bash
git clone https://github.com/alishokri1661s/open-webui.git
cd open-webui
git checkout arena/40390d46-open-webui
```

این شاخه شامل تمام کدهای این قابلیت است:

```
backend/open_webui/utils/intel.py      ← موتور Elasticsearch، تشخیص خودکار فیلدها، مسیر پرواز
backend/open_webui/routers/intel.py    ← مسیرهای API زیر /api/v1/intel
src/lib/components/intel/              ← رابط کاربری سه حالت
src/lib/intel/topic.ts                 ← تعریف «موضوع X» (اینجا را ویرایش می‌کنی)
src/routes/(app)/intel/+page.svelte    ← مسیر /intel
```

---

## ۲. نصب بک‌اند (Python)

```bash
python3 -m venv .venv
source .venv/bin/activate           # macOS/Linux
# Windows: .venv\Scripts\activate

pip install --upgrade pip
pip install -r backend/requirements.txt
```

نصب کامل حدود ۳ تا ۶ دقیقه طول می‌کشد.

### اگر سیستم‌ات ضعیف است (بدون GPU / RAM کم)

`requirements.txt` دو بستهٔ سنگین دارد که برای این پروژه لازم نیست (`sentence-transformers` که تورچ را
می‌آورد و `playwright` که مرورگر دانلود می‌کند). نسخهٔ سبک را بساز:

```bash
grep -vE "^(sentence-transformers|playwright)" backend/requirements.txt > /tmp/reqs-slim.txt
pip install -r /tmp/reqs-slim.txt
```

> ⚠️ فقط `backend/requirements-slim.txt` را نصب نکن؛ آن نسخه برای بوت شدن کافی نیست
> (`chromadb` و چند بستهٔ دیگر کم دارد).

---

## ۳. نصب فرانت‌اند (Node)

```bash
npm install
```

اگر با خطای SSL مواجه شدی (`UNABLE_TO_VERIFY_LEAF_SIGNATURE` یا خطای شبکه در اسکریپت‌های نصب):

```bash
npm install --ignore-scripts --no-audit --no-fund
```

> پکیج‌های `leaflet`، `topojson-client` و `world-atlas` (برای نقشهٔ آفلاین) از قبل در
> `package.json` هستند و با همین دستور نصب می‌شوند.

---

## ۴. فایل تنظیمات `.env`

یک فایل به نام `.env` در **ریشهٔ پروژه** بساز:

```bash
nano .env
```

محتوای پیشنهادی (کمینهٔ لازم برای اجرای آفلاین):

```dotenv
# ---------- عمومی ----------
WEBUI_SECRET_KEY=یک-رشته-تصادفی-طولانی-و-ثابت
DATA_DIR=./data
OFFLINE_MODE=true
ENABLE_VERSION_UPDATE_CHECK=false

# ---------- مدل محلی (یکی از دو حالت) ----------
# الف) Ollama
ENABLE_OLLAMA_API=true
OLLAMA_BASE_URL=http://localhost:11434

# ب) هر سرور سازگار با OpenAI (llama.cpp / vLLM / LM Studio / ...)
# ENABLE_OPENAI_API=true
# OPENAI_API_BASE_URLS=http://127.0.0.1:8000/v1
# OPENAI_API_KEYS=sk-local

# ---------- فضای Intelligence ----------
INTEL_ENABLE=true
INTEL_DEMO_MODE=auto
INTEL_DEFAULT_LOOKBACK_HOURS=24

# ---------- Elasticsearch (اختیاری — بدون آن حالت دمو فعال می‌شود) ----------
INTEL_ELASTICSEARCH_URL=http://localhost:9200
INTEL_ELASTICSEARCH_INDEX=flights
INTEL_ELASTICSEARCH_USERNAME=elastic
INTEL_ELASTICSEARCH_PASSWORD=changeme
```

نکته‌های مهم:

- `WEBUI_SECRET_KEY` را **ثابت** نگه دار. اگر با هر بار اجرا عوض شود، همهٔ توکن‌ها باطل می‌شوند و
  مرورگر مدام با خطای 401 به صفحهٔ ورود برمی‌گردد.
- نام متغیرها مهم است: `INTEL_ENABLE` (نه `INTEL_ENABLED`).
- `INTEL_DEMO_MODE` سه مقدار دارد: `auto` (اگر URL تنظیم نشده باشد دمو روشن است)، `on`، `off`.
- اگر Elasticsearch با API Key کار می‌کند، به‌جای یوزر/پسورد از
  `INTEL_ELASTICSEARCH_API_KEY=...` استفاده کن.

---

## ۵. اجرا — روش الف: حالت توسعه (توصیه‌شده)

دو ترمینال باز کن.

**ترمینال ۱ — بک‌اند (پورت 8080):**

```bash
cd open-webui
source .venv/bin/activate
export PYTHONPATH=backend
uvicorn open_webui.main:app --host 0.0.0.0 --port 8080
```

اگر فایل `.env` را نساخته‌ای، همین‌جا هم می‌توانی متغیرها را بدهی:

```bash
WEBUI_SECRET_KEY=dev-secret-please-change DATA_DIR=./data OFFLINE_MODE=true \
INTEL_ENABLE=true INTEL_DEMO_MODE=auto \
PYTHONPATH=backend uvicorn open_webui.main:app --host 0.0.0.0 --port 8080
```

**ترمینال ۲ — فرانت‌اند (پورت 5173):**

```bash
cd open-webui
npm run dev
```

سپس مرورگر را باز کن:

```
http://localhost:5173
```

در این حالت Vite هر درخواست `/api/...` را به `http://localhost:8080` منتقل می‌کند (در
`vite.config.ts` تنظیم شده) و تغییرات کد فرانت‌اند بدون ری‌استارت اعمال می‌شود.

> اگر دستور `npm run dev` در محیط بدون اینترنت روی مرحلهٔ `pyodide:fetch` گیر کرد، مستقیم اجرا کن:
> `npx vite dev --host`

---

## ۶. اجرا — روش ب: تک‌پورت / شبیه Production

در این روش فرانت‌اند کامپایل می‌شود و خودِ بک‌اند آن را روی پورت 8080 سرو می‌کند (نیاز به دو ترمینال
نیست):

```bash
# ۱) ساخت نسخهٔ نهایی فرانت‌اند (به حافظهٔ زیاد نیاز دارد)
npm run build

# ۲) اجرای بک‌اند؛ چون پوشهٔ build وجود دارد، خودش فرانت‌اند را سرو می‌کند
source .venv/bin/activate
export PYTHONPATH=backend
uvicorn open_webui.main:app --host 0.0.0.0 --port 8080
```

سپس:

```
http://localhost:8080
```

> ⚠️ `npm run build` حافظه‌بر است (اسکریپت با `--max-old-space-size=12288` اجرا می‌شود). اگر سیستم
> کمتر از ۸ گیگ RAM دارد، از **روش الف** استفاده کن؛ همان تجربهٔ کامل را می‌دهد.

---

## ۷. اولین ورود و ساخت حساب مدیر

1. آدرس `/auth` را باز کن (`http://localhost:5173/auth` یا `http://localhost:8080/auth`).
2. روی **Sign up** برو و اولین حساب را بساز.
3. **اولین حسابی که ساخته می‌شود، به‌طور خودکار نقش `admin` می‌گیرد.**
4. در نوار کنار سایت، ورودی **Intelligence / اطلاعات و تحلیل** (سومی، پین‌شده) را بزن یا مستقیم برو به:

```
/intel
```

در صفحهٔ شروع، یکی از سه حالت را انتخاب کن:

| حالت | کاربرد |
| --- | --- |
| **کارشناس موضوع** | پرسش‌وپاسخ تخصصی دربارهٔ «موضوع X» |
| **اطلاعات پروازها** | جدول پروازهای Elasticsearch + نقشهٔ مسیر + چت دربارهٔ هواپیماهای انتخاب‌شده |
| **تحلیل فایل** | آپلود PDF/DOCX/CSV/JSON/MD و پرسش دربارهٔ محتوای آن |

---

## ۸. اتصال مدل هوش مصنوعی محلی

### گزینهٔ ۱ — Ollama (ساده‌ترین)

```bash
ollama serve
ollama pull llama3.1:8b
```

سپس در رابط کاربری: **Admin Panel → Settings → Connections → Ollama API** و آدرس
`http://localhost:11434` را ثبت کن (یا همان `OLLAMA_BASE_URL` در `.env` کافی است).

### گزینهٔ ۲ — سرور سازگار با OpenAI

اگر `llama.cpp`, `vLLM`, `LM Studio` یا `text-generation-webui` داری، در `.env`:

```dotenv
ENABLE_OPENAI_API=true
OPENAI_API_BASE_URLS=http://127.0.0.1:8000/v1
OPENAI_API_KEYS=sk-local
```

بعد از فعال شدن، مدل‌ها در انتخاب‌گر مدل (بالای هر تب در `/intel`) دیده می‌شوند.

اگر هیچ مدلی وصل نکنی، رابط بالا می‌آید ولی چت خطا می‌دهد؛ جدول و نقشهٔ Elasticsearch مستقل از مدل
کار می‌کنند.

---

## ۹. اتصال Elasticsearch

### ۹.۱ تنظیم آدرس

حداقل این چهار متغیر را در `.env` بگذار و بک‌اند را ری‌استارت کن:

```dotenv
INTEL_ELASTICSEARCH_URL=http://localhost:9200
INTEL_ELASTICSEARCH_INDEX=flights
INTEL_ELASTICSEARCH_USERNAME=elastic
INTEL_ELASTICSEARCH_PASSWORD=changeme
```

### ۹.۲ ببین سیستم فیلدها را درست تشخیص داده یا نه

```bash
curl -s http://localhost:8080/api/v1/intel/meta?force=1 | python3 -m json.tool
```

در خروجی، بخش `fields` باید فیلدهای واقعی ایندکس تو را نشان دهد (زمان، شناسه، مختصات، مسیر…).
تشخیص خودکار بر اساس نام‌های رایج انجام می‌شود؛ اگر ایندکس تو نام‌های غیرمعمول دارد، دستی مشخص کن:

```dotenv
INTEL_TIME_FIELD=@timestamp
INTEL_ID_FIELD=flight_id
INTEL_CALLSIGN_FIELD=callsign
INTEL_LAT_FIELD=position.lat
INTEL_LON_FIELD=position.lon
INTEL_ALT_FIELD=position.alt
INTEL_SPEED_FIELD=velocity
INTEL_HEADING_FIELD=heading
INTEL_STATUS_FIELD=status
INTEL_TRAJECTORY_FIELD=trajectory
INTEL_QUERY_FIELDS=callsign,origin,destination,registration
```

### ۹.۳ نکتهٔ مهم دربارهٔ فیلد `trajectory`

مسیر هر هواپیما از کلید `trajectory` خوانده می‌شود و می‌تواند یکی از این شکل‌ها باشد:

- آرایهٔ نقاط: `[{"lat":…,"lon":…,"alt":…,"ts":…}, …]`
- رشتهٔ GeoJSON
- رشتهٔ فشرده (`lat,lon;lat,lon;…`)
- WKT (`LINESTRING (lon lat, …)`)

اگر مسیر داخل سند وجود نداشته باشد، نقشه فقط نقطهٔ فعلی هواپیما را نشان می‌دهد.

### ۹.۴ حالت دمو

اگر Elasticsearch وصل نباشد و `INTEL_DEMO_MODE=auto` باشد، تب پروازها با دادهٔ ساختگی (۲۴ هواپیما،
برچسب «Demo» در رابط) کار می‌کند تا بتوانی جدول + نقشه + چت را قبل از وصل‌کردن دادهٔ واقعی ببینی.
برای خاموش کردن: `INTEL_DEMO_MODE=off`.

---

## ۱۰. تغییر «موضوع X»

تمام متن‌های حالت کارشناس در **یک فایل** است:

```
src/lib/intel/topic.ts
```

- `ACTIVE_TOPIC_ID` تعیین می‌کند کدام موضوع فعال باشد.
- چهار موضوع آماده وجود دارد: `strategic` (هوانوردی و ژئوپلیتیک)، `economics`، `politics`، `culture`.
- برای ساخت موضوع جدید، یک عضو به `TOPICS` اضافه کن:

```ts
{
  id: 'energy',
  badge: 'EN',
  name: { en: 'Energy Markets', fa: 'بازار انرژی' },
  tagline: { en: 'Oil, gas and power balances', fa: 'نفت، گاز و تراز برق' },
  description: { en: '…', fa: '…' },
  systemPrompt: { en: `You are an energy markets analyst…`, fa: `تو یک تحلیلگر بازار انرژی هستی…` },
  suggestions: { en: ['…'], fa: ['…'] }
}
```

سپس:

```ts
export const ACTIVE_TOPIC_ID = 'energy';
```

فایل را ذخیره کن؛ در حالت توسعه فقط مرورگر را رفرش کن (بدون ری‌استارت). در حالت Production یک‌بار
`npm run build` لازم است.

> می‌توانی بدون دست‌زدن به کد هم موضوع را از سمت سرور عوض کنی:
> `INTEL_TOPIC_NAME`، `INTEL_TOPIC_PROMPT` و `INTEL_TOPIC_SUGGESTIONS` (با کاما جدا شود).

---

## ۱۱. بررسی سلامت

پس از ورود، توکن بگیر و این‌ها را امتحان کن:

```bash
TOKEN=$(curl -s -X POST http://localhost:8080/api/v1/auths/signin \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"your-password"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["token"])')

# وضعیت فضای Intelligence و اتصال Elasticsearch
curl -s -H "Authorization: Bearer $TOKEN" http://localhost:8080/api/v1/intel/health

# ۱۲ ردیف آخرین ۲۴ ساعت
curl -s -H "Authorization: Bearer $TOKEN" \
  "http://localhost:8080/api/v1/intel/flights?hours=24" | python3 -m json.tool | head -40
```

خروجی سالم چیزی شبیه این است:

```json
{"enabled": true, "ok": true, "source": "elasticsearch", "doc_count": 1284}
```

اگر `"source": "demo"` دیدی یعنی به Elasticsearch وصل نشده و داری دادهٔ ساختگی می‌بینی.

---

## ۱۲. عیب‌یابی

| نشانه | علت | راه‌حل |
| --- | --- | --- |
| `ModuleNotFoundError: chromadb` هنگام بوت | نسخهٔ ناقص وابستگی‌ها | `pip install -r backend/requirements.txt` (کامل) |
| `npm install` با `UNABLE_TO_VERIFY_LEAF_SIGNATURE` | پروکسی/فایروال SSL را قطع می‌کند | `npm install --ignore-scripts --no-audit --no-fund` |
| `npm run build` با `JavaScript heap out of memory` | RAM کم | از **روش الف (حالت توسعه)** استفاده کن یا `NODE_OPTIONS=--max-old-space-size=8192` |
| صفحهٔ سفید / `502 Bad Gateway` | سرور توسعه مرده است | ترمینال `npm run dev` را دوباره اجرا کن، بعد `Ctrl+Shift+R` |
| بعد از ورود، همه‌چیز `401 Not authenticated` | توکن قدیمی در `localStorage` (مثلاً بعد از ری‌ست دیتابیس) | DevTools → Application → Clear site data (یا `localStorage.clear()`) و دوباره Login؛ مطمئن شو `WEBUI_SECRET_KEY` ثابت است |
| در `/intel` پیام ۴۰۴ | `INTEL_ENABLE=false` | `INTEL_ENABLE=true` و ری‌استارت بک‌اند |
| هیچ مدلی در انتخاب‌گر مدل نیست | سرور مدل وصل نیست | `ollama serve` یا `OPENAI_API_BASE_URLS` را چک کن |
| جدول پروازها خالی است | بازهٔ زمانی یا فیلد زمان اشتباه | بازه را در جدول بزرگ‌تر کن؛ `INTEL_TIME_FIELD` را تنظیم کن |
| نقشه چیزی نشان نمی‌دهد | فیلد `trajectory` خالی/با نام دیگر | `INTEL_TRAJECTORY_FIELD` را تنظیم کن؛ کاشی‌های آفلاین به‌صورت پیش‌فرض داخلی هستند |
| بک‌اند با `OFFLINE_MODE` روی دانلود مدل embedding گیر می‌کند | تلاش برای دانلود مدل از HuggingFace | `OFFLINE_MODE=true` و `RAG_EMBEDDING_ENGINE=openai` (یا `ollama`) |

### پاک‌کردن و شروع از صفر

```bash
deactivate 2>/dev/null
rm -rf .venv node_modules build data
# سپس از مرحلهٔ ۲ دوباره شروع کن
```

---

## پیوست: اسکریپت اجرای سریع (Linux/macOS)

اگر می‌خواهی همهٔ مراحل نصب را یک‌جا انجام دهی، این را در ریشهٔ پروژه ذخیره کن و اجرا کن:

```bash
#!/usr/bin/env bash
set -e
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
grep -vE "^(sentence-transformers|playwright)" backend/requirements.txt > /tmp/reqs-slim.txt
pip install -r /tmp/reqs-slim.txt
npm install --ignore-scripts --no-audit --no-fund
echo "✅ نصب تمام شد. برای اجرا: ./run.sh"
```

و برای اجرای روزمره:

```bash
#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"
source .venv/bin/activate
export PYTHONPATH=backend
uvicorn open_webui.main:app --host 0.0.0.0 --port 8080 &
sleep 3
npm run dev
```

---

## مستندات بیشتر

- `INTEL.md` — مرجع کامل متغیرهای محیطی، شکل دادهٔ Elasticsearch و مسیرهای API
- `README.md` — معرفی کلی پروژه
