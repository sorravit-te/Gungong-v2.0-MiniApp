"""Gemini AI service for fraud detection - converted from test.ipynb."""

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate
from typing import Literal, Dict, Any
import os
import asyncio
import json
import re
from concurrent.futures import ThreadPoolExecutor
from ..core.config import settings


# Classification types - Updated for new format
FraudClassification = Literal["FRAUD_GAMBLING", "SCAM_MALICIOUS", "SAFE_NORMAL"]


# Comprehensive prompt template covering all 9 fraud categories
FRAUD_DETECTION_PROMPT = """
**System/Instruction:**
You are "Gun Gong" (กันโกง), an AI security expert. Analyze the input text and classify the risk.

**CORE ARCHETYPES (4 Groups):**

1. **FINANCIAL FRAUD** (High Risk):
   - **Investment:** Guaranteed high returns, AI trading, "easy money".
   - **Loan:** Fast approval, no credit check, blacklist OK.
   - **Shopping:** Unrealistic cheap prices, no COD, urgency.
   - **Prize/Romance:** You won a prize (pay fee first), Foreigner needs help/money.
   - *Keywords:* กำไรแน่นอน, กู้เงินด่วน, ราคาหลุดโลก, ผู้โชคดี, โอนก่อน

2. **IMPERSONATION** (Very High Risk):
   - Claims to be Police, Bank, Post Office, or Authority.
   - Demands urgent action (transfer money, click link, verify identity).
   - *Keywords:* ตำรวจ, สรรพากร, บัญชีถูกระงับ, พัสดุตกค้าง, ยืนยันตัวตน

3. **MALICIOUS CONTENT** (High Risk):
   - **Gambling:** Slots, Baccarat, Free Credit, "Spin", Betting URLs.
   - **Adult:** Porn, 18+, Sex services.
   - *Keywords:* สล็อต, บาคาร่า, เครดิตฟรี, หนังโป๊, 18+

4. **SAFE / NORMAL** (Safe):
   - **Casual Chat:** Greetings, opinions, daily life ("I hate gambling").
   - **Informational:** News, Warnings, Reviews, Educational content.
   - **Legit Domains:** YouTube, Facebook, Shopee, Official Banks.

**DECISION LOGIC:**
1. **Analyze Intent:** Is it Promotion/Deception (Risk) or Opinion/News (Safe)?
2. **Check Context:** "I hate gambling" = Safe. "Play gambling here" = Fraud.
3. **Verdict:** If Intent is Safe -> SAFE_NORMAL. If Intent is Fraud -> Classify Category.

**Output Format (JSON):**
{{
  "reasoning_summary": "Concise 1-sentence explanation of intent and risk factors.",
  "category": "FRAUD_GAMBLING" | "SCAM_MALICIOUS" | "SAFE_NORMAL",
  "risk_level": "High" | "Medium" | "Low",
  "confidence_score": (0-100),
  "reason_th": "Short Thai explanation for the user.",
  "keywords_found": ["list", "of", "keywords"]
}}

**Input Text:**
---
{message}
---

**JSON Response:**
"""


EDUCATIONAL_CONTENT_PROMPT = """
**System/Instruction:**
You are "Gun Gong" (กันโกง), an AI security expert. Your task is to analyze the user's input text/message.

**VERY IMPORTANT CONTEXT: This message has been pre-identified as a potential NEWS ARTICLE, EDUCATIONAL CONTENT, or a WARNING about scams. Your primary goal is to distinguish between legitimate informational content and an actual scam.**

*   If it is **legitimate news, a knowledge article, or a warning**, you MUST classify it as **SAFE_NORMAL**, even if it contains keywords related to scams, finance, or law. Look for neutral, informative language and the absence of urgent, promotional calls to action.
*   If it is **a scam disguised as news or an article** (e.g., using a fake news format to promote a fraudulent investment), you must classify it as **SCAM_MALICIOUS**. Look for urgent calls to action, unrealistic promises, or links to suspicious sites.

**Analyze based on this special context. Is the following text a legitimate article or an actual scam?**

═══════════════════════════════════════════════════════════════════════════════

**🟢 SAFE MESSAGES - These are NORMAL conversations:**

1. **Normal Money Requests** (SAFE - no red flags):
   ✅ "ขอเงินหน่อย" (asking for money)
   ✅ "ยืมเงินพ่อ 500 บาท" (borrow money from dad)
   ✅ "โอนเงินให้เพื่อน" (transfer money to friend)
   ✅ "ขอยืมเงิน 1000 บาท" (borrow 1000 baht)
   ✅ "พ่อโอนเงินให้หน่อย" (dad please transfer money)

2. **Legitimate News/Reviews/Warnings** (SAFE - informational):
   ✅ "ข่าว: ตำรวจบุกจับแก๊งโกงออนไลน์"
   ✅ "รีวิว: ระวังเว็บพนันออนไลน์หลอกลวง"
   ✅ "เตือน! พบสแกมแจกเครดิตฟรี"
   ✅ "บทความ: วิธีสังเกตเว็บพนันปลอม"

3. **Casual Mentions** (SAFE - no promotional intent):
   ✅ "วันนี้ไปดูบอล แทงบอลไหม" (casual chat about betting)
   ✅ "เพื่อนชวนไปคาสิโนปอยเปต" (talking about casino visit)
   ✅ "เล่นสล็อตที่คาสิโนมาครับ" (mentioned playing slots)

4. **Safe Domains** (SAFE - legitimate websites):
   ✅ YouTube, Facebook, Instagram, Twitter, TikTok, LINE official
   ✅ Shopee, Lazada, Amazon (legitimate e-commerce)
   ✅ Government/news websites

═══════════════════════════════════════════════════════════════════════════════

**🔴 FRAUD/SCAM CATEGORIES - Need MULTIPLE red flags:**

**1. IMPERSONATION_AUTHORITY** (Severity: ⚠️⚠️⚠️ VERY HIGH)
   Red Flags Required: Authority claim + Urgency/Threat + Action demand

   Examples:
   ❌ "แจ้งจากตำรวจ บัญชีของคุณพัวพันคดีฟอกเงิน กรุณาโอนเงินไปบัญชีนี้เพื่อตรวจสอบ"
      (HAS: police claim + money laundering threat + transfer demand)

   ❌ "เจ้าหน้าที่ธนาคารแจ้ง: บัญชีของคุณถูกระงับ กรุณายืนยันตัวตนที่ลิงก์นี้"
      (HAS: bank employee claim + account suspended + link action)

   ❌ "มีพัสดุตกค้างที่ไปรษณีย์ กรุณาชำระค่าธรรมเนียม 299 บาท"
      (HAS: postal authority + payment demand)

   Keywords: ตำรวจ, สภ., DSI, ปปง, สรรพากร, เจ้าหน้าที่ธนาคาร, ไปรษณีย์, พัสดุตกค้าง, บัญชีถูกระงับ

**2. PHISHING_CREDENTIAL** (Severity: ⚠️⚠️⚠️ VERY HIGH)
   Red Flags Required: Credential request + Urgency + Link/Action

   Examples:
   ❌ "ยืนยันตัวตนด่วน! บัญชีของคุณจะถูกระงับใน 24 ชม. คลิก: https://bit.ly/xxxxx"
      (HAS: verify identity + urgency + suspicious link)

   ❌ "ระบบปรับปรุง กรุณากรอกรหัสผ่านและ OTP เพื่อยืนยัน"
      (HAS: system update + password/OTP request)

   ❌ "บัตรของคุณหมดอายุ กรุณาอัพเดทข้อมูลบัญชี"
      (HAS: expiry claim + update account demand)

   Keywords: ยืนยันตัวตน, กรอกรหัสผ่าน, OTP, อัพเดทข้อมูล, หมดอายุ, ระบบปรับปรุง

**3. LOAN_SHARK** (Severity: ⚠️⚠️ HIGH)
   Red Flags Required: Loan offer + Unrealistic promise (no credit check/instant approval) + Urgency

   Examples:
   ❌ "กู้เงินด่วน! อนุมัติใน 10 นาที ไม่เช็คเครดิต แบล็คลิสกู้ได้"
      (HAS: urgent loan + instant approval + blacklist OK)

   ❌ "สินเชื่อไม่ต้องหลักฐาน อนุมัติ 100% รับเงินใน 24 ชม"
      (HAS: no documents + 100% approval + quick money)

   ❌ "เงินด่วน 24 ชม ไม่ผ่านธนาคาร กู้ที่นี่"
      (HAS: emergency loan + bypass banks)

   Keywords: กู้เงินด่วน, อนุมัติ 100%, แบล็คลิส, ไม่ต้องหลักฐาน, ไม่เช็คเครดิต

**4. INVESTMENT_SCAM** (Severity: ⚠️⚠️ HIGH)
   Red Flags Required: Investment offer + Guaranteed profit/unrealistic ROI + Urgency/Easy money

   Examples:
   ❌ "ลงทุน Forex รับประกันกำไร 30% ต่อเดือน ระบบ AI เทรดให้"
      (HAS: forex + guaranteed 30% + AI trading claim)

   ❌ "Bitcoin ทำเงินวันละ 5000 บาท กำไรแน่นอน 50% ROI 1 เดือน"
      (HAS: bitcoin + daily 5k + guaranteed 50% ROI)

   ❌ "ลงทุนขั้นต่ำ 1000 บาท รับคืน 5000 บาท คูณทุน 5 เท่า"
      (HAS: min investment + 5x return + multiply capital)

   Keywords: กำไรแน่นอน, รับประกันกำไร, ROI, คูณทุน, Forex, Bitcoin, ทำเงินวันละ

**5. JOB_SCAM** (Severity: ⚠️ MEDIUM-HIGH)
   Red Flags Required: Job offer + Unrealistic salary (>50k for simple work) + No experience needed

   Examples:
   ❌ "งานที่บ้าน เดือนละ 50000 บาท ไม่ต้องประสบการณ์ รับสมัครไม่จำกัดอายุ"
      (HAS: work from home + 50k salary + no experience + unlimited age)

   ❌ "ทำแบบสำรวจได้เงิน กด like share รับเงิน วันละ 500 บาท งาน part time ง่าย"
      (HAS: survey/like tasks + daily 500 + easy job)

   ❌ "กด like share รับเงิน พิมพ์งานรายได้ดี work from home 30k"
      (HAS: like/share + typing job + 30k salary)

   Keywords: งานที่บ้าน, เดือนละ 50000+, ไม่ต้องประสบการณ์, กด like share, ทำแบบสำรวจได้เงิน

**6. SHOPPING_FRAUD** (Severity: ⚠️ MEDIUM)
   Red Flags Required: Product sale + Unrealistic price + No COD/Transfer only + Urgency

   Examples:
   ❌ "iPhone 15 Pro Max ของแท้ 100% ราคา 3500 บาท ไม่รับ COD โอนเท่านั้น"
      (HAS: iPhone + unrealistic 3500 price + authentic claim + no COD)

   ❌ "Flash Sale! Samsung ราคา 999 บาท สต็อกจำกัด รีบโอนก่อน"
      (HAS: flash sale + unrealistic 999 price + limited stock + urgency)

   ✅ "ขาย iPhone 15 Pro Max 35000 บาท รับ COD" (SAFE - realistic price, accepts COD)

   Keywords: ของแท้ 100%, ราคาพิเศษ, ไม่รับ COD, โอนเท่านั้น, สต็อกจำกัด, Flash Sale

**7. PRIZE_SCAM** (Severity: ⚠️ MEDIUM)
   Red Flags Required: Prize claim + Large amount + Fee demand/Urgency + No prior participation

   Examples:
   ❌ "ยินดีด้วย! คุณถูกรางวัลที่ 1 รับเงิน 1000000 บาท กดรับด่วน"
      (HAS: lottery winner + 1M prize + urgent claim)

   ❌ "โชคดี! ผู้โชคดีรับของรางวัล โอนค่าธรรมเนียม 299 บาทเพื่อรับรางวัล"
      (HAS: lucky winner + prize + fee to claim)

   ❌ "ได้รับสิทธิ์รับของฟรี แจกรางวัลกดรับด่วน"
      (HAS: free prize + urgency)

   Keywords: ถูกรางวัล, ยินดีด้วย, โชคดี, ผู้โชคดี, แจกรางวัล, กดรับด่วน

**8. ROMANCE_SCAM** (Severity: ⚠️ MEDIUM)
   Red Flags Required: Romance/dating + Foreign partner + Money request/Help needed

   Examples:
   ❌ "ทหารอเมริกันหาคู่ มรดกต่างประเทศต้องการความช่วยเหลือโอนเงิน"
      (HAS: US soldier + inheritance + money transfer help)

   ❌ "หาแฟนต่างชาติ sugar daddy รายได้ 50000 บาทต่อเดือน"
      (HAS: foreign partner + sugar daddy + high income promise)

   ❌ "แฟนต่างชาติส่งของให้ ต้องจ่ายค่าภาษี 5000 บาท"
      (HAS: foreign partner + package + customs fee demand)

   Keywords: ทหารอเมริกัน, มรดกต่างประเทศ, sugar daddy, แฟนต่างชาติ, ค่าภาษี

**9. ADULT_CONTENT** (Severity: ⚠️⚠️ HIGH)
   Red Flags Required: Adult website domain OR Explicit adult keywords + Service offer

   **IMPORTANT: Adult website URLs are ALWAYS flagged as SCAM_MALICIOUS**

   Examples:
   ❌ "https://www.xvideos.es/" (HAS: adult website domain - xvideos)
   ❌ "https://pornhub.com" (HAS: adult website domain - pornhub)
   ❌ "ดูหนังโป๊ที่ xnxx" (HAS: adult website domain - xnxx)

   ❌ "หนังโป๊ไทย xxx videos porn free คลิปเด็ด 18+"
      (HAS: porn keywords + xxx + 18+)

   ❌ "บริการสาว call girl นวดพิเศษ massage happy ending"
      (HAS: call girl service + special massage)

   ❌ "sex chat webcam girl private only fans leak"
      (HAS: sex chat + webcam + onlyfans)

   **Adult Website Domains (ALWAYS flag as dangerous):**
   xvideos, pornhub, xnxx, xhamster, redtube, youporn, tube8, spankbang,
   eporner, txxx, hqporner, sex.com, porn.com, adult.com, xxx.com, javhd, jav

   Keywords: หนังโป๊, xxx, porn, sex chat, call girl, นวดพิเศษ, webcam girl, adult domains

**10. GAMBLING** (Severity: ⚠️ MEDIUM - if promoted with link/contact)
   Red Flags Required: Gambling website/promotion + URL/LINE ID + Incentive (free credit/bonus)

   Examples:
   ❌ "สล็อต ufabet เครดิตฟรี 1000 บาท ฝากถอนออโต้ คลิก https://ufabet999.com"
      (HAS: gambling site name + free credit + deposit/withdraw + URL)

   ❌ "บาคาร่า sbobet แตกง่าย โบนัส 100% LINE: @abc123"
      (HAS: gambling game + site name + bonus + LINE ID)

   ✅ "เพื่อนชวนไปคาสิโนปอยเปต" (SAFE - casual mention, no promotion)
   ✅ "วันนี้ไปดูบอล แทงบอลไหม" (SAFE - casual chat, no link/promo)

   Keywords: ufabet, sbobet, สล็อต+URL, เครดิตฟรี+link, ฝากถอน+contact

═══════════════════════════════════════════════════════════════════════════════

**DECISION LOGIC:**

1. **Check for DANGEROUS domains first (HIGHEST PRIORITY):**
   - Contains adult website (xvideos, pornhub, xnxx, etc.) → SCAM_MALICIOUS (High confidence 75-85%)
   - Contains gambling website with URL (ufabet, sbobet + link) → FRAUD_GAMBLING (High confidence 75-85%)

2. **Check for SAFE signals:**
   - Contains safe domain (YouTube, Facebook, Shopee, etc.) → SAFE_NORMAL
   - News/review/warning context (ข่าว, รีวิว, เตือน, ระวัง) → SAFE_NORMAL
   - Normal conversation (<20 words, no suspicious keywords) → SAFE_NORMAL

3. **Count red flags:**
   - 0-1 red flags → SAFE_NORMAL (Low confidence)
   - 2 red flags → SCAM_MALICIOUS or FRAUD_GAMBLING (Medium confidence 40-70%)
   - 3+ red flags → SCAM_MALICIOUS or FRAUD_GAMBLING (High confidence 70-95%)

4. **Category selection:**
   - If adult website domain detected → SCAM_MALICIOUS
   - If gambling-related (ufabet, sbobet, slots + URL/LINE) → FRAUD_GAMBLING
   - All other scams → SCAM_MALICIOUS
   - Otherwise → SAFE_NORMAL

5. **Confidence scoring:**
   - SAFE messages: 0-30%
   - Medium risk (2 red flags): 40-70%
   - High risk (3+ red flags): 70-95%
   - Adult/Gambling websites: 75-85%

═══════════════════════════════════════════════════════════════════════════════

**Output Format:**
You must respond strictly in JSON format as follows:
{{
  "category": "FRAUD_GAMBLING" | "SCAM_MALICIOUS" | "SAFE_NORMAL",
  "risk_level": "High" | "Medium" | "Low",
  "confidence_score": (0-100),
  "reason_th": "อธิบายสั้นๆ ภาษาไทยว่าทำไมถึงอันตราย หรือปลอดภัย (เช่น มีคำชักชวนเล่นพนันพร้อมลิงก์, มีการปลอมตัวเป็นเจ้าหน้าที่ธนาคาร, เป็นการสนทนาปกติ)",
  "keywords_found": ["list", "of", "suspicious", "keywords", "found"]
}}

**Input Text to Analyze:**
---
{message}
---

**JSON Response:**
"""

class GeminiFraudDetector:
    """
    Fraud detection using Gemini AI.

    Converted from test.ipynb with the same logic and prompt.
    """

    def __init__(self, api_key: str | None = None, model: str | None = None):
        """
        Initialize Gemini fraud detector.

        Args:
            api_key: Google API key. If None, uses settings.google_api_key
            model: Gemini model name. If None, uses settings.gemini_model
        """
        self.api_key = api_key or settings.google_api_key
        self.model = model or settings.gemini_model

        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found")

        # Initialize LLM (same as notebook)
        self.llm = ChatGoogleGenerativeAI(
            model=self.model,
            temperature=0,
            api_key=self.api_key,
        )

        # Create prompt template (same as notebook)
        self.prompt = PromptTemplate(
            input_variables=["message"],
            template=FRAUD_DETECTION_PROMPT,
        )

        # Create prompt template for educational content
        self.educational_prompt = PromptTemplate(
            input_variables=["message"],
            template=EDUCATIONAL_CONTENT_PROMPT,
        )

    def classify_message(self, message: str) -> Dict[str, Any]:
        """
        Classify a message as fraud, scam, or safe (returns JSON).

        Args:
            message: The message text to classify.

        Returns:
            Dict with classification details:
            {
                "category": "FRAUD_GAMBLING" | "SCAM_MALICIOUS" | "SAFE_NORMAL",
                "risk_level": "High" | "Medium" | "Low",
                "confidence_score": 0-100,
                "reason_th": "คำอธิบายภาษาไทย",
                "keywords_found": ["list", "of", "keywords"]
            }

        Raises:
            Exception: If Gemini API fails or returns invalid response.
        """
        try:
            # Format prompt with message
            formatted_input = self.prompt.format(message=message)

            # Invoke Gemini
            response = self.llm.invoke(formatted_input)

            # Extract response content
            content = response.content.strip()

            # Try to parse JSON
            try:
                # Extract JSON from response (handle markdown code blocks)
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group(0)
                    result = json.loads(json_str)
                else:
                    # Fallback: try parsing entire content
                    result = json.loads(content)

                # Validate required fields
                required_fields = ["category", "risk_level", "confidence_score", "reason_th", "keywords_found"]
                # reasoning_summary is optional but preferred
                
                if not all(field in result for field in required_fields):
                    raise ValueError("Missing required fields in JSON response")

                # Validate category
                valid_categories = ["FRAUD_GAMBLING", "SCAM_MALICIOUS", "SAFE_NORMAL"]
                if result["category"] not in valid_categories:
                    print(f"⚠️  Invalid category: {result['category']}, defaulting to SAFE_NORMAL")
                    result["category"] = "SAFE_NORMAL"

                return result

            except (json.JSONDecodeError, ValueError) as e:
                # JSON parsing failed - log and return default safe response
                print(f"⚠️  Failed to parse JSON response: {e}")
                print(f"Raw response: {content}")

                return {
                    "category": "SAFE_NORMAL",
                    "risk_level": "Low",
                    "confidence_score": 0,
                    "reason_th": "ไม่สามารถวิเคราะห์ได้",
                    "keywords_found": [],
                    "reasoning_summary": "JSON Parse Error"
                }

        except Exception as e:
            raise Exception(f"Gemini classification failed: {str(e)}")

    async def classify_message_async(self, message: str) -> Dict[str, Any]:
        """
        Async version: Classify a message as fraud, scam, or safe.

        Args:
            message: The message text to classify.

        Returns:
            Dict with classification details (same as classify_message)
        """
        # Run sync method in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.classify_message, message)

    async def classify_with_details_async(self, message: str) -> dict:
        """
        Async version: Classify a message and return detailed results.

        Args:
            message: The message text to classify.

        Returns:
            dict with full classification details + metadata
        """
        result = await self.classify_message_async(message)

        # Add metadata
        result["message_length"] = len(message)
        result["model"] = self.model
        result["is_fraud"] = result["category"] in ["FRAUD_GAMBLING", "SCAM_MALICIOUS"]
        result["is_safe"] = result["category"] == "SAFE_NORMAL"

        return result

    def classify_with_details(self, message: str) -> dict:
        """
        Classify a message and return detailed results.

        Args:
            message: The message text to classify.

        Returns:
            dict with full classification details + metadata
        """
        result = self.classify_message(message)

        # Add metadata
        result["message_length"] = len(message)
        result["model"] = self.model
        result["is_fraud"] = result["category"] in ["FRAUD_GAMBLING", "SCAM_MALICIOUS"]
        result["is_safe"] = result["category"] == "SAFE_NORMAL"

        return result

    def classify_educational_content(self, message: str) -> Dict[str, Any]:
        """
        Classifies a message using the special educational content prompt.
        This is for messages pre-screened as potential articles or news.
        """
        try:
            # Use the educational prompt
            formatted_input = self.educational_prompt.format(message=message)
            response = self.llm.invoke(formatted_input)
            content = response.content.strip()

            # The rest of the parsing logic is identical to classify_message
            try:
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    json_str = json_match.group(0)
                    result = json.loads(json_str)
                else:
                    result = json.loads(content)

                required_fields = ["category", "risk_level", "confidence_score", "reason_th", "keywords_found"]
                if not all(field in result for field in required_fields):
                    raise ValueError("Missing required fields in JSON response")

                valid_categories = ["FRAUD_GAMBLING", "SCAM_MALICIOUS", "SAFE_NORMAL"]
                if result["category"] not in valid_categories:
                    print(f"⚠️  Invalid category from educational prompt: {result['category']}, defaulting to SAFE_NORMAL")
                    result["category"] = "SAFE_NORMAL"

                return result
            except (json.JSONDecodeError, ValueError) as e:
                print(f"⚠️  Failed to parse JSON from educational prompt: {e}")
                print(f"Raw response: {content}")
                return {
                    "category": "SAFE_NORMAL",
                    "risk_level": "Low",
                    "confidence_score": 10, # Give a bit of confidence as it's likely safe
                    "reason_th": "ไม่สามารถวิเคราะห์บทความได้",
                    "keywords_found": []
                }
        except Exception as e:
            raise Exception(f"Gemini educational classification failed: {str(e)}")

    async def classify_educational_content_async(self, message: str) -> Dict[str, Any]:
        """Async version of classify_educational_content."""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self.classify_educational_content, message)

    async def classify_educational_with_details_async(self, message: str) -> dict:
        """Async educational classification with detailed results."""
        result = await self.classify_educational_content_async(message)
        result["message_length"] = len(message)
        result["model"] = self.model
        result["is_fraud"] = result["category"] in ["FRAUD_GAMBLING", "SCAM_MALICIOUS"]
        result["is_safe"] = result["category"] == "SAFE_NORMAL"
        result["prompt_type"] = "educational" # Add metadata for debugging
        return result


# Singleton instance (optional, for convenience)
_detector_instance = None


def get_fraud_detector() -> GeminiFraudDetector:
    """Get or create singleton fraud detector instance."""
    global _detector_instance
    if _detector_instance is None:
        _detector_instance = GeminiFraudDetector()
    return _detector_instance