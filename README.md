# 🛡️ GunGong (กันโกง) - AI Fraud Detection Bot

LINE Bot ที่ใช้ Gemini AI และเทคโนโลยีหลายชั้นเพื่อตรวจจับข้อความฉ้อโกง Spam, Phishing และการหลอกลวง พร้อม LIFF Mini App สำหรับตรวจสอบลิงก์ บัญชีธนาคาร เบอร์โทรศัพท์ และวิเคราะห์ภาพอัจฉริยะ

---

## 📱 เริ่มใช้งาน LINE Bot

### วิธีเพิ่มเพื่อน GunGong Bot

1. **ค้นหา LINE ID: @357asclq**
   หรือคลิกลิงก์: https://line.me/R/ti/p/@357asclq

2. **กดเพิ่มเพื่อน** และเริ่มส่งข้อความได้เลย!

---

## 👥 วิธีใช้งานสำหรับผู้ใช้ทั่วไป

### 💬 1. ตรวจสอบข้อความต้องสงสัย

**ส่งข้อความตรง ๆ ไปที่บอทได้เลย**

```
ตัวอย่าง:
"🎰 สมัครคาสิโนออนไลน์ รับโบนัส 100%"
```

บอทจะตอบกลับทันทีว่า:
- 🚨 ข้อความนี้เป็นฉ้อโกงหรือไม่
- 📊 ระดับความเสี่ยง (ต่ำ/กลาง/สูง/วิกฤต)
- 💡 เหตุผลว่าทำไมถึงอันตราย
- ⚠️ คำแนะนำในการป้องกัน

### 🔗 2. ตรวจสอบลิงก์ต้องสงสัย

**ส่งลิงก์มาให้บอทตรวจสอบ**

```
ตัวอย่าง:
"https://bit.ly/xxxxx"
"line.me/R/xxxxx"
```

บอทจะ:
- 🔍 เปิดลิงก์จริง (ถ้าเป็น short URL)
- 🛡️ ตรวจสอบกับ VirusTotal
- 🎯 วิเคราะห์ด้วย Gemini AI
- ⚡ บอกผลภายใน 3-8 วินาที

### 📷 3. ตรวจสอบภาพ (ฟีเจอร์ใหม่! 🆕)

**ส่งรูปภาพที่ต้องสงสัยมาได้เลย**

บอทจะวิเคราะห์อัตโนมัติว่าเป็น:

#### 📱 **QR Code**
```
ส่งภาพ QR Code → บอทจะ:
✅ อ่าน QR Code และแปลงเป็นลิงก์
✅ ตรวจสอบว่าลิงก์อันตรายหรือไม่
✅ เตือนถ้าพบว่าเป็น Phishing/Scam
```

#### 🪪 **บัตรประชาชน**
```
ส่งภาพบัตรประชาชน → บอทจะ:
✅ แสกนข้อมูลด้วย OCR (Gemini Vision)
✅ ตรวจสอบเลข 13 หลัก (checksum)
✅ ตรวจสอบกับฐานข้อมูล blacklist
✅ บอกว่าปลอดภัยหรือมีประวัติฉ้อโกง
```

#### 🖼️ **รูปทั่วไป**
```
ส่งรูปสัตว์เลี้ยง, อาหาร, คน, ทิวทัศน์
→ บอทจะไม่ตอบกลับ (ไม่รบกวน)
```

### 🏦 4. ตรวจสอบบัญชีธนาคาร

**เปิด LIFF Mini App** (กดเมนูด้านล่างใน LINE)

```
1. เลือก "🏦 Check Bank Account"
2. ใส่เลขบัญชี (เช่น 123-4-56789-0)
3. เลือกธนาคาร (KBANK, SCB, BBL, ฯลฯ)
4. กด "ตรวจสอบ"
```

ระบบจะบอกว่า:
- ✅ บัญชีปลอดภัย หรือ
- 🚨 เป็นบัญชีมิจฉาชีพ (มีประวัติรับเงินโกง)

### ☎️ 5. ตรวจสอบเบอร์โทรศัพท์

**เปิด LIFF Mini App**

```
1. เลือก "☎️ Check Phone Number"
2. ใส่เบอร์ (เช่น 081-234-5678)
3. กด "ตรวจสอบ"
```

ระบบจะบอกว่า:
- จำนวนครั้งที่ถูกรายงาน
- ประเภทการฉ้อโกง (โทรหลอกลวง, นายหน้าเงินกู้นอกระบบ)
- ระดับความเสี่ยง

### 📜 6. ดูประวัติการตรวจสอบ

**เปิด LIFF Mini App → "📜 View History"**

ดูย้อนหลังว่าเคยตรวจอะไรบ้าง พร้อมผลลัพธ์

---

## 🎯 Features

### 🤖 AI Detection Capabilities
- ✅ โฆษณาการพนันออนไลน์ (FRAUD_GAMBLING_AD)
- ✅ Phishing/มัลแวร์ (SCAM_MALICIOUS)
- ✅ หลอกลวงทางการเงิน (FRAUD_FINANCIAL)
- ✅ ข่าวลวง (FRAUD_FAKE_NEWS)
- ✅ โฆษณาสินค้าปลอม (FRAUD_PRODUCT)
- ✅ เนื้อหาสำหรับผู้ใหญ่ (ADULT_CONTENT)
- ✅ ข้อความปลอดภัย (SAFE_NORMAL)

### 📸 Intelligent Image Analysis (NEW! 🆕)
- ✅ **QR Code Detection** - แสกน QR Code และตรวจสอบลิงก์ที่อันตราย
- ✅ **ID Card OCR** - อ่านบัตรประชาชนไทยและตรวจสอบ blacklist
- ✅ **Smart Filtering** - ไม่รบกวนเมื่อส่งรูปทั่วไป (สัตว์เลี้ยง, อาหาร, คน)

### 🔧 Technology Stack
- 🤖 **Gemini 2.5 Flash** - AI Text Classification
- 👁️ **Gemini Vision** - Intelligent Image Analysis
- 🔍 **VirusTotal** - Malicious URL Detection
- 🎯 **Pattern Matching** - Instant Recognition
- 📊 **TF-IDF** - Similarity Analysis
- 🌐 **Playwright** - Headless Browser Scraping
- 🔤 **Homoglyph Detection** - Unicode Spoofing Detection
- 🔥 **Firestore** - Database & Caching

### 🌐 User Interfaces
- 📱 **LINE Official Account** - Chat with Bot
  - 💬 Text Message Analysis
  - 🔗 URL Verification
  - 📷 Image Classification (QR/ID Card/General)
- 🌐 **LIFF Mini App** - Web Interface
  - 🔗 Check Link
  - 📱 Check SMS
  - 📷 Scan QR Code
  - 🏦 Check Bank Account
  - ☎️ Check Phone Number
  - 📜 View History

---

## 📁 Project Structure

```
gungong/
├── src/
│   ├── backend/
│   │   ├── main.py                      # FastAPI app (145 lines) ✨
│   │   ├── routers/                     # API Endpoints (9 routers)
│   │   │   ├── health.py               # Health check
│   │   │   ├── blacklist.py            # Bank/Phone verification
│   │   │   ├── history.py              # Cache & Feedback
│   │   │   ├── fraud.py                # Fraud detection & URL check
│   │   │   ├── fraud_v2.py             # Fraud detection v2
│   │   │   ├── conversation.py         # Conversation analysis
│   │   │   ├── verification.py         # Multi-verification hub
│   │   │   └── webhook.py              # LINE webhook handler
│   │   ├── utils/                       # Helper functions (4 files)
│   │   │   ├── message_helpers.py      # Message analysis helpers
│   │   │   ├── flex_templates.py       # LINE Flex Message templates
│   │   │   └── thai_id_validator.py    # Thai ID validation
│   │   ├── core/
│   │   │   ├── config.py               # Environment config
│   │   │   ├── models.py               # Pydantic models
│   │   │   ├── fraud_detector.py       # AI fraud detection logic
│   │   │   ├── fraud_patterns.json     # Pattern matching rules
│   │   │   └── performance_config.py   # Performance optimization
│   │   └── services/                    # External services (21 services)
│   │       ├── gemini_service.py       # Gemini AI
│   │       ├── line_service.py         # LINE Messaging API
│   │       ├── virustotal_service.py   # VirusTotal scanning
│   │       ├── database_service.py     # Firestore operations
│   │       ├── prescreen_service.py    # Pattern matching
│   │       ├── similarity_service.py   # TF-IDF analysis
│   │       ├── headless_scraper_service.py  # Browser scraping
│   │       ├── gambling_detector_service.py # Gambling detection
│   │       ├── homoglyph_detector_service.py # Unicode spoofing
│   │       ├── blacklist_service.py    # Bank/Phone blacklist
│   │       ├── feedback_service.py     # User feedback
│   │       ├── image_classifier_service.py  # Image classification
│   │       ├── id_card_service.py      # ID card verification
│   │       ├── verification_service.py # Verification orchestration
│   │       ├── conversation_analyzer_service.py # Conversation analysis
│   │       └── ...                     # และอื่นๆ
│   └── frontend/                        # React LIFF Mini App
│       ├── index.html
│       ├── src/
│       │   ├── components/             # React Components
│       │   │   ├── home.jsx            # Home page
│       │   │   ├── history.jsx         # History page
│       │   │   ├── IDCardScanner.jsx   # ID Card scanner
│       │   │   ├── ScanImage.jsx       # Image scanner
│       │   │   └── ...
│       │   ├── utils/                  # Utility functions
│       │   │   ├── firebase.js         # Firebase config
│       │   │   └── liff.js             # LIFF SDK helpers
│       │   └── styles/                 # CSS styles
│       └── public/                      # Static assets
├── config/                               # Configuration files
│   ├── firebase.json
│   ├── firestore.indexes.json
│   └── firestore.rules
├── deployment/                           # Deployment files
│   ├── Dockerfile
│   ├── Dockerfile.fullstack
│   ├── docker-compose.yml
│   ├── cloudbuild.yaml
│   ├── cloudbuild-fullstack.yaml
│   └── cloudbuild-build-only.yaml
├── .env.example                          # Environment template
├── requirements.txt
├── pyproject.toml
└── secrets/
    └── service-account.json             # Firebase credentials (not in git)
```

**Architecture**: Modular FastAPI backend with router-based organization following best practices

---

## 🚀 Quick Start

### Option 1: Docker Compose (แนะนำ!) ⭐

```bash
# 1. Setup environment
cp .env.example .env
nano .env

# 2. Add Firebase credentials
# Download service-account.json from Firebase Console
# Place at: secrets/service-account.json

# 3. Start services
cd deployment
docker-compose up -d --build

# 4. Get ngrok URL
open http://localhost:4040

# 5. Configure LINE webhook
# Webhook URL: https://your-ngrok-url.ngrok-free.app/webhook
```

### Option 2: Manual Setup (Development)

```bash
# 1. Clone & Install
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

# 2. Setup environment
cp .env.example .env
# Edit .env with your credentials

# 3. Run server
uvicorn src.backend.main:app --reload --port 8000
```

---

## 🔑 Required Credentials

### 1. Gemini API Key
- Visit: https://aistudio.google.com/apikey
- Create API key
- Add to `.env`: `GOOGLE_API_KEY=your_key`

### 2. LINE Bot
- Visit: https://developers.line.biz/console/
- Create Messaging API Channel
- Get credentials:
  - `LINE_CHANNEL_ACCESS_TOKEN=your_token`
  - `LINE_CHANNEL_SECRET=your_secret`
  - `LINE_LIFF_ID=your_liff_id`

### 3. Firebase
- Visit: https://console.firebase.google.com/
- Create project → Enable Firestore
- Download service account key → `secrets/service-account.json`
- Get project ID → `FIRESTORE_PROJECT_ID=your_project_id`
- Get Firebase web app credentials for frontend:
  - `VITE_FIREBASE_API_KEY=your_firebase_api_key`
  - `VITE_FIREBASE_PROJECT_ID=your_project_id`
  - และอื่นๆ (ดูใน `.env.example`)

### 4. VirusTotal (Optional)
- Visit: https://www.virustotal.com/
- Create account → Get API key
- Add to `.env`: `VIRUSTOTAL_API_KEY=your_key`

---

## 📚 API Documentation

### Main Endpoints

| Method | Endpoint | Description | Router |
|--------|----------|-------------|--------|
| GET | `/` | Serve frontend | main.py |
| GET | `/health` | Health check | health.py |
| POST | `/check-fraud` | AI fraud detection | fraud.py |
| POST | `/check-url` | URL verification | fraud.py |
| POST | `/analyze-message` | TF-IDF analysis | fraud.py |
| POST | `/check-bank` | Bank account check | blacklist.py |
| POST | `/check-phone` | Phone number check | blacklist.py |
| POST | `/api/v2/verify-phone` | Phone verification (v2) | verification.py |
| POST | `/api/v2/verify-bank` | Bank verification (v2) | verification.py |
| POST | `/api/v2/verify-social` | Social profile check | verification.py |
| POST | `/api/v2/verify-id-card` | ID card OCR + verify | verification.py |
| POST | `/api/v2/verify-id-number` | ID number only verify | verification.py |
| GET | `/cache-entries` | History (paginated) | history.py |
| GET | `/history/{id}` | Single history entry | history.py |
| GET | `/cache-stats` | Cache statistics | history.py |
| POST | `/feedback` | User feedback | history.py |
| POST | `/webhook` | LINE webhook | webhook.py |

**Swagger UI**: http://localhost:8000/docs  
**ReDoc**: http://localhost:8000/redoc

---

## 🔄 System Flow

### Text Message Flow
```
User Message
    │
    ▼
┌─────────────────┐
│  Cache Check    │ → Hit? → Return (< 50ms)
└────────┬────────┘
         │ Miss
         ▼
┌─────────────────────────┐
│  Pre-screening          │
│  • Pattern matching     │
│  • URL expansion        │
│  • Homoglyph check      │
└────────┬────────────────┘
         │
         ▼
┌─────────────────────────┐
│   Routing Strategy      │
│   Instant/AI/Full       │
└────────┬────────────────┘
         │
         ▼
┌──────────────────────────┐
│   Parallel Execution     │
├──────────┬───────────────┤
│ Gemini AI│ VirusTotal    │
│  (3-5s)  │  (2-4s)       │
└──────────┴───────────────┘
         │
         ▼
┌─────────────────┐
│ Combine Results │
│ Save to Cache   │
└────────┬────────┘
         │
         ▼
     Response
```

### Image Message Flow (NEW! 🆕)
```
User Image
    │
    ▼
┌─────────────────────────┐
│  Image Classification   │
│  (Gemini Vision)        │
│  • QR Code?             │
│  • ID Card?             │
│  • General Photo?       │
└────────┬────────────────┘
         │
         ├─→ QR Code ─────────┐
         │                    ▼
         │            ┌───────────────┐
         │            │ Decode QR URL │
         │            │ Check Fraud   │
         │            └───────────────┘
         │
         ├─→ ID Card ─────────┐
         │                    ▼
         │            ┌───────────────┐
         │            │ OCR Scan      │
         │            │ Checksum Test │
         │            │ Blacklist Chk │
         │            └───────────────┘
         │
         └─→ General ─────────┐
                              ▼
                      ┌──────────────┐
                      │ No Response  │
                      │ (Don't spam) │
                      └──────────────┘
```

### Routing Strategy

| Confidence | Strategy | Actions | Speed |
|------------|----------|---------|-------|
| ≥ 90% | Instant | Pattern only | < 500ms |
| 50-89% | AI Only | Skip URL check | 3-5s |
| < 50% | Full | AI + URL | 5-8s |

---

## ⚡ Performance

### Metrics

| Metric | Value |
|--------|-------|
| Avg Response Time | 2.1s |
| Cache Hit Ratio | 65% |
| API Cost per 1K req | $0.035 |
| Fraud Detection Accuracy | 95%+ |

### Optimization Features

- ✅ Firestore caching (30-day TTL)
- ✅ Parallel AI + URL checking
- ✅ Pattern pre-screening
- ✅ Router-based code organization
- ✅ Rate limiting per endpoint

---

## 🗄️ Database Schema

### Firestore Collections

| Collection | Purpose | TTL |
|------------|---------|-----|
| `fraud_check_cache` | Cache AI results | 30 days |
| `history` | User check history | Permanent |
| `fraud_messages` | Fraud database (TF-IDF) | Permanent |
| `gambling_domains` | Domain blacklist | Permanent |
| `feedback_logs` | User feedback | Permanent |

---

## 🧪 Testing

### 1. Fraud Detection API Test

```bash
curl -X POST http://localhost:8000/check-fraud \
  -H "Content-Type: application/json" \
  -d '{
    "message": "🎰 สมัครคาสิโนออนไลน์ รับโบนัส 100%"
  }'
```

Expected Response:
```json
{
  "category": "FRAUD_GAMBLING_AD",
  "risk_level": "High",
  "is_fraud": true,
  "confidence_score": 95,
  "reason_th": "โฆษณาการพนันออนไลน์"
}
```

### 2. ID Card Verification API Test (NEW! 🆕)

```bash
# Read image as base64
IMAGE_BASE64=$(base64 -i test_id_card.jpg)

curl -X POST http://localhost:8000/api/v2/verify-id-card \
  -H "Content-Type: application/json" \
  -d "{
    \"image_base64\": \"$IMAGE_BASE64\"
  }"
```

Expected Response:
```json
{
  "id_number": "1234567890123",
  "is_valid_format": true,
  "is_blacklisted": false,
  "is_safe": true,
  "reports_count": 0,
  "risk_level": "LOW",
  "extracted_data": {
    "id_number": "1234567890123",
    "name_th": "สมชาย",
    "surname_th": "ใจดี",
    "date_of_birth": "1990-05-15",
    "address": "123 ถนนสุขุมวิท..."
  }
}
```

### 3. Phone/Bank Verification Test

```bash
# Phone verification
curl -X POST http://localhost:8000/api/v2/verify-phone \
  -H "Content-Type: application/json" \
  -d '{"phone": "0812345678"}'

# Bank verification
curl -X POST http://localhost:8000/api/v2/verify-bank \
  -H "Content-Type: application/json" \
  -d '{"account_number": "1234567890", "bank_code": "KBANK"}'
```

### 4. LINE Webhook Test

1. Start server: `uvicorn src.backend.main:app --reload --port 8000`
2. Start ngrok: `ngrok http 8000`
3. Configure LINE webhook: `https://xxxx.ngrok-free.app/webhook`
4. Send text message, image, or QR code to bot

---

## 🐳 Docker Commands

```bash
# Navigate to deployment folder
cd deployment

# Start all services
docker-compose up -d

# View logs
docker-compose logs -f gungong-bot

# View ngrok Web UI
open http://localhost:4040

# Restart
docker-compose restart

# Stop
docker-compose stop

# Clean up
docker-compose down
```

---

## 💡 Real-World Use Cases

### 🛒 For Online Shoppers
```
Scenario: ได้รับข้อความโปรโมชั่นพร้อมลิงก์
Action: Forward ข้อความไปที่ GunGong Bot
Result: บอทตรวจสอบลิงก์และเตือนถ้าเป็น Phishing
```

### 💰 For Transfer Money
```
Scenario: จะโอนเงินให้คนที่ไม่รู้จัก
Action: ใช้ LIFF App ตรวจสอบเลขบัญชี + เบอร์โทร
Result: ได้รู้ว่าเป็นบัญชีมิจฉาชีพหรือไม่
```

### 📱 For QR Code Payments
```
Scenario: แสกน QR Code จากร้านค้าที่ไม่รู้จัก
Action: ถ่ายภาพ QR Code และส่งให้บอท
Result: บอทอ่าน QR และเตือนถ้าเป็นลิงก์อันตราย
```

### 🆔 For Document Verification
```
Scenario: ผู้ประกอบการต้องตรวจสอบบัตรประชาชนลูกค้า
Action: ถ่ายภาพบัตรประชาชนและส่งให้บอท
Result: บอทแสกนข้อมูล + ตรวจสอบว่ามีประวัติฉ้อโกงหรือไม่
```

### 👥 For Group Chats
```
Scenario: มีคนส่งข้อความน่าสงสัยในกลุ่ม
Action: แท็ก @GunGong พร้อมข้อความ
Result: บอททำงานในกลุ่มและเตือนสมาชิกทุกคน
```

---

## 🔐 Security Features

- ✅ Rate limiting per endpoint
- ✅ CORS configuration
- ✅ LINE signature verification
- ✅ Input sanitization
- ✅ Environment-based configs

---

## 📈 Monitoring

### Logs

```bash
# View logs directory
ls -la logs/

# Tail log file
tail -f logs/gungong_$(date +%Y%m%d).log
```

### Log Levels
- **DEBUG**: Development details
- **INFO**: Operational events (Cache HIT, API calls)
- **WARNING**: Degraded performance (VirusTotal unavailable)
- **ERROR**: Critical failures

---

## 🔧 Troubleshooting

### Common Issues

**Import Error**
```bash
# Run from project root
cd /Users/analeotic/Desktop/project/personal/gungong
uvicorn src.backend.main:app --reload
```

**LINE Webhook Not Working**
1. Check ngrok is running: `curl http://localhost:4040/api/tunnels`
2. Verify webhook URL in LINE console
3. Check LINE credentials in `.env`

**Gemini API Error**
- Verify `GOOGLE_API_KEY` in `.env`
- Check quota: https://aistudio.google.com/

**Firestore Connection Error**
- Verify `secrets/service-account.json` exists
- Check `FIRESTORE_PROJECT_ID` in `.env`

---

## 🎯 Architecture Principles

1. **Modular Design** - Router-based architecture (FastAPI best practice)
2. **Fail-Safe** - Always return safe result on error
3. **Multi-Layer Caching** - Firestore + Pre-screen
4. **Parallel Execution** - AI + URL checks run simultaneously
5. **Event-Driven** - Webhook → Pre-screen → Route → Detect → Respond

---

## 📝 Recent Updates

### v2.1.0 - Intelligent Image Analysis (2026-01-11) 🆕
- ✅ Added Gemini Vision AI for image classification
- ✅ QR Code detection and fraud checking
- ✅ Thai ID Card OCR and verification
- ✅ Smart filtering (no response for general photos)
- ✅ Integrated image classifier service
- ✅ Updated verification router with image endpoints

### v2.0.0 - Modular Refactoring (2025-12-01)
- ✅ Refactored main.py from 1,662 lines → 145 lines (91% reduction)
- ✅ Created router-based architecture (9 routers: health, blacklist, history, fraud, fraud_v2, conversation, verification, webhook)
- ✅ Added utils module for helper functions (message_helpers, flex_templates, thai_id_validator)
- ✅ Expanded services to 21+ specialized services
- ✅ Improved code maintainability and scalability
- ✅ Implemented mention-based group message processing
- ✅ Migrated frontend to React with modern component architecture

### v1.0.0 - Initial Release
- ✅ Gemini AI integration
- ✅ LINE Bot + LIFF Mini App
- ✅ Firestore caching
- ✅ Multi-layer detection

---

## 📄 License

MIT

---

## 🤝 Contributing

This is a personal project, but suggestions and feedback are welcome!

---

## 📞 Support

For questions or issues, please check:
- 📖 Code comments in routers
- 📊 API documentation at `/docs`
- 🔍 Debug logs in `logs/` directory

---

**Made with ❤️ for safer online communication in Thailand**
