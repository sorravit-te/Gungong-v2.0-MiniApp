"""Fraud detection router with AI-based analysis and URL checking."""

import asyncio
import re
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..services.gemini_service import get_fraud_detector
from ..services.database_service import get_database_service
from ..services.virustotal_service import get_virustotal_service
from ..services.fraud_message_service import get_fraud_message_service
from ..services.similarity_service import get_similarity_service
from ..services.prescreen_service import get_prescreen_service
from ..core.logger import get_logger

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
logger = get_logger(__name__)


class FraudCheckRequest(BaseModel):
    """Request model for fraud checking."""
    message: str
    user_id: Optional[str] = None


@router.post("/analyze-message")
@limiter.limit("15/minute")
async def analyze_message(http_request: Request, request: FraudCheckRequest):
    """
    Analyze message and provide detailed report including:
    - How many times this message was seen
    - Danger percentage compared to fraud messages in database (using TF-IDF)
    - Similar fraud messages

    Example:
        POST /analyze-message
        {
            "message": "คลิกรับเงิน 50,000 บาท"
        }

    Returns:
        {
            "frequency": {
                "seen_before": true,
                "times_seen": 5,
                "first_seen": "2025-01-20...",
                "classification": "FRAUD_GAMBLING_AD"
            },
            "danger_analysis": {
                "danger_percentage": 85.5,
                "most_similar_message": "คลิกรับเงิน...",
                "similarity_score": 0.855,
                "total_fraud_messages": 50,
                "similar_messages": [...]
            }
        }
    """
    similarity_service = get_similarity_service()

    if not similarity_service:
        raise HTTPException(
            status_code=503,
            detail="Similarity service not configured. Please set DATABASE_URL in .env"
        )

    try:
        # 1. Check message frequency
        frequency = similarity_service.check_message_frequency(request.message)

        # 2. Calculate danger score using TF-IDF
        danger_analysis = similarity_service.calculate_danger_score(request.message)

        return {
            "message": request.message,
            "frequency": frequency,
            "danger_analysis": danger_analysis
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.post("/check-fraud")
@limiter.limit("10/minute")
async def check_fraud(request: Request, fraud_request: FraudCheckRequest):
    """
    Check if a message is fraudulent (with database caching and URL scanning).

    This endpoint:
    1. Checks database cache first (if configured)
    2. If cache miss, checks message content using Gemini AI
    3. Checks URLs in message using VirusTotal (if configured)
    4. Saves result to cache for future use

    Example:
        POST /check-fraud
        {
            "message": "คลิกรับเงิน 50,000 บาท"
        }

    Returns:
        {
            "category": "SCAM_MALICIOUS",
            "risk_level": "High",
            "confidence_score": 95,
            "reason_th": "ข้อความมีลิงก์ที่น่าสงสัย",
            "keywords_found": ["คลิก", "รับเงิน"],
            "is_fraud": true,
            "is_safe": false,
            "cached": false,
            "url_check": {
                "has_urls": true,
                "malicious_urls": ["http://phishing-site.com"],
                "is_dangerous": true
            }
        }
    """
    try:
        # 1. Check database cache first
        db_service = get_database_service()
        cached_result = None

        if db_service:
            cached_result = db_service.get_cached_result(fraud_request.message)

            if cached_result:
                logger.info(f"✅ Cache HIT for message (hash: {db_service.hash_message(fraud_request.message)[:8]}...)")

                # Save to history log even on cache hit
                if fraud_request.user_id:
                    db_service.save_history(
                        user_id=fraud_request.user_id,
                        message=fraud_request.message,
                        classification=cached_result.get("category"),
                        is_fraud=cached_result.get("is_fraud"),
                        is_safe=cached_result.get("is_safe"),
                        confidence_score=cached_result.get("confidence_score"),
                        reason=cached_result.get("reason_th"),
                        reasoning_summary=cached_result.get("reasoning_summary"),
                        url_check_result=cached_result.get("url_check"),
                        has_malicious_urls=cached_result.get("has_malicious_urls"),
                        model_used=cached_result.get("model")
                    )
                    logger.debug(f"📜 Saved cache hit to history for user {fraud_request.user_id}")

                return cached_result

        logger.info(f"⚠️  Cache MISS - checking with AI...")

        # 2. Get fraud detector
        detector = get_fraud_detector()

        # 3. Prepare tasks for parallel execution
        ai_task = detector.classify_with_details_async(fraud_request.message)

        # Task 2: URL Checking
        vt_service = get_virustotal_service()
        url_task = None

        if vt_service:
            url_task = vt_service.check_text_for_malicious_urls_async(fraud_request.message)

        # 4. Execute in parallel
        logger.debug(f"⚡ Starting parallel execution for message: {fraud_request.message[:20]}...")
        import time
        start_time = time.time()

        results = await asyncio.gather(ai_task, url_task if url_task else asyncio.sleep(0))

        result = results[0]
        url_check = results[1] if url_task else None

        if url_check is None and vt_service:
             url_check = {"error": "URL check skipped"}

        execution_time = time.time() - start_time
        logger.info(f"⚡ Parallel execution finished in {execution_time:.2f}s")

        # 5. Combine results
        response = {
            **result,
            "url_check": url_check,
            "cached": False,
            "execution_time": execution_time
        }

        # 6. Check and save adult websites from prescreen
        prescreen_service = get_prescreen_service()
        prescreen_result = prescreen_service.check_message(fraud_request.message)

        if db_service and prescreen_result.matched_patterns:
            adult_patterns = [p for p in prescreen_result.matched_patterns if "adult_websites" in p]
            if adult_patterns:
                try:
                    from urllib.parse import urlparse

                    url_pattern = r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+'
                    urls = re.findall(url_pattern, fraud_request.message)

                    for url in urls:
                        try:
                            parsed = urlparse(url)
                            domain = parsed.netloc or parsed.path.split('/')[0]

                            if domain and any(adult_keyword in domain.lower() for adult_keyword in ['xvideos', 'pornhub', 'xnxx', 'xhamster', 'redtube', 'youporn', 'tube8', 'spankbang', 'eporner', 'txxx', 'hqporner', 'porn', 'xxx', 'adult', 'sex', 'javhd', 'jav']):
                                db_service.save_malicious_domain(
                                    domain=domain,
                                    confidence=0.9,
                                    category="adult_content",
                                    source="pattern_detection"
                                )
                                print(f"💾 Saved adult website domain to blacklist: {domain} (confidence: 0.90)")
                        except Exception as url_error:
                            print(f"⚠️  Failed to extract domain from {url}: {url_error}")
                except Exception as e:
                    print(f"⚠️  Failed to save adult website domain: {e}")

        # 7. Upgrade fraud level if malicious URLs found
        has_malicious_urls = False
        if url_check and url_check.get("is_dangerous"):
            response["is_fraud"] = True
            response["is_safe"] = False
            response["url_threat_detected"] = True
            has_malicious_urls = True

            # If message was SAFE but has malicious URL, upgrade to SCAM
            if result["category"] == "SAFE_NORMAL":
                response["category"] = "SCAM_MALICIOUS"
                response["risk_level"] = "High"
                response["reason_th"] = "ข้อความมี URL ที่เป็นอันตราย (Malicious URL detected)"
                if "malicious_url" not in response.get("keywords_found", []):
                    response["keywords_found"].append("malicious_url")

            # Save malicious/gambling domains to blacklist
            if db_service:
                try:
                    from urllib.parse import urlparse

                    dangerous_urls = url_check.get("malicious_urls", []) + url_check.get("gambling_urls", [])

                    for url in dangerous_urls:
                        try:
                            parsed = urlparse(url)
                            domain = parsed.netloc or parsed.path.split('/')[0]

                            if domain:
                                is_malicious = url in url_check.get("malicious_urls", [])
                                is_gambling = url in url_check.get("gambling_urls", [])

                                if is_malicious:
                                    confidence = 1.0
                                    category = "malicious_url"
                                    source = "virustotal"

                                    for detail in url_check.get("details", []):
                                        if detail["url"] == url and "/" in detail.get("detections", ""):
                                            parts = detail["detections"].split("/")
                                            if len(parts) == 2 and parts[1].isdigit():
                                                malicious_count = int(parts[0])
                                                total_engines = int(parts[1])
                                                if total_engines > 0:
                                                    confidence = min(1.0, malicious_count / total_engines)

                                elif is_gambling:
                                    confidence = 0.8
                                    category = "gambling"
                                    source = "gambling_detector"

                                    for detail in url_check.get("details", []):
                                        if detail["url"] == url:
                                            confidence = detail.get("gambling_confidence", 0.8)

                                db_service.save_malicious_domain(
                                    domain=domain,
                                    confidence=confidence,
                                    category=category,
                                    source=source
                                )
                                print(f"💾 Saved {category} domain to blacklist: {domain} (confidence: {confidence:.2f})")

                        except Exception as url_error:
                            print(f"⚠️  Failed to extract domain from {url}: {url_error}")

                except Exception as e:
                    print(f"⚠️  Failed to save malicious domain to blacklist: {e}")

        # 8. Save result to cache AND history
        if db_service:
            # Save to history log
            if fraud_request.user_id:
                try:
                    msg_type = "text"
                    if has_malicious_urls or (url_check and url_check.get("has_urls")):
                        msg_type = "link"

                    db_service.save_history(
                        user_id=fraud_request.user_id,
                        message=fraud_request.message,
                        classification=response.get("category"),
                        is_fraud=response.get("is_fraud"),
                        is_safe=response.get("is_safe"),
                        confidence_score=response.get("confidence_score"),
                        reason=response.get("reason_th"),
                        reasoning_summary=response.get("reasoning_summary"),
                        url_check_result=url_check,
                        has_malicious_urls=has_malicious_urls,
                        model_used=response.get("model"),
                        message_type=msg_type
                    )
                    logger.debug(f"📜 Saved result to history for user {fraud_request.user_id}")
                except Exception as e:
                    logger.error(f"⚠️  Failed to save history: {e}")

            # Save to cache
            try:
                db_service.save_result(
                    message=fraud_request.message,
                    classification=response["category"],
                    is_fraud=response["is_fraud"],
                    is_safe=response["is_safe"],
                    confidence_score=result.get("confidence_score"),
                    reason=response.get("reason_th"),
                    url_check_result=url_check,
                    has_malicious_urls=has_malicious_urls,
                    model_used=response["model"],
                    user_id=fraud_request.user_id,
                    cache_ttl_days=30
                )
                logger.debug(f"💾 Result saved to cache")
            except Exception as e:
                logger.error(f"⚠️  Failed to save to cache: {e}")

        # 9. Save to fraud_messages table
        if response["is_fraud"]:
            fraud_service = get_fraud_message_service()
            if fraud_service:
                try:
                    save_result = fraud_service.save_fraud_message(
                        message_text=fraud_request.message,
                        category=response["category"],
                        confidence_score=response.get("confidence_score"),
                        keywords=response.get("keywords_found", [])
                    )
                    if save_result["saved"]:
                        logger.info(f"💾 New fraud message saved (unique)")
                    else:
                        logger.debug(f"💾 Fraud message updated (similarity: {save_result.get('similarity', 0):.2%}, hit_count incremented)")
                except Exception as e:
                    logger.error(f"⚠️  Failed to save fraud message: {e}")

        return response

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Fraud detection failed: {str(e)}")


@router.post("/check-url")
@limiter.limit("15/minute")
async def check_url(request: Request, url_request: FraudCheckRequest):
    """
    Check if URLs in a message are malicious using VirusTotal.

    This is a lightweight check that only uses VirusTotal, not the full AI model.
    """
    # Extract URLs from message
    urls = extract_urls(url_request.message)
    if not urls:
        return {
            "is_safe": True,
            "is_fraud": False,
            "confidence_score": 0.0,
            "category": "SAFE_NORMAL",
            "reason_th": "ไม่พบลิงก์ในข้อความ",
            "url_check": {
                "has_urls": False,
                "urls_found": [],
                "malicious_urls": [],
                "gambling_urls": [],
                "is_dangerous": False,
                "details": []
            }
        }

    try:
        # Get VirusTotal service
        vt_service = get_virustotal_service()

        if vt_service is None:
            raise HTTPException(
                status_code=503,
                detail="VirusTotal service not configured. Please set VIRUSTOTAL_API_KEY in .env"
            )

        # Check URLs in message
        result = vt_service.check_text_for_malicious_urls(url_request.message)

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"URL check failed: {str(e)}")
