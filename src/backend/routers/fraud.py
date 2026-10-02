"""Fraud detection router with AI-based analysis and URL checking."""

import asyncio
import hashlib
import re
from time import monotonic
from datetime import datetime, timezone
from typing import Literal, Optional
from fastapi import APIRouter, BackgroundTasks, Request, HTTPException
from pydantic import BaseModel
from slowapi import Limiter
from slowapi.util import get_remote_address

from ..services.gemini_service import get_fraud_detector
from ..services.database_service import get_database_service
from ..services.virustotal_service import get_virustotal_service
from ..services.fraud_message_service import get_fraud_message_service
from ..services.similarity_service import get_similarity_service
from ..services.prescreen_service import get_prescreen_service
from ..services.url_safety_service import URLSafetyError, normalize_user_url
from ..services.url_verification_service import POLICY_VERSION, get_url_verification_service
from ..services.url_risk_evidence_service import lookup_recent_risk, save_recent_risk
from ..core.performance_config import get_performance_config
from ..core.config import settings
from ..core.logger import get_logger
from ..services.user_identity_service import require_user

router = APIRouter()
limiter = Limiter(key_func=get_remote_address)
logger = get_logger(__name__)


HistoryMessageType = Literal["link", "text", "sms", "qr"]


class FraudCheckRequest(BaseModel):
    """Request model for fraud checking."""
    message: str
    user_id: Optional[str] = None
    message_type: Optional[HistoryMessageType] = None


def _resolve_history_message_type(
    requested_type: Optional[HistoryMessageType],
    url_check: Optional[dict],
    has_malicious_urls: bool = False,
) -> Optional[str]:
    """Resolve history metadata without changing fraud analysis behavior."""
    if requested_type:
        return "text" if requested_type == "sms" else requested_type

    if has_malicious_urls or (url_check and url_check.get("has_urls")):
        return "link"

    # Let DatabaseService preserve its existing link/text auto-detection.
    return None


def _link_cache_key(normalized_url: str) -> str:
    policy = (f"{settings.url_trusted_origins}:{settings.url_reputation_provider}:"
              f"{settings.url_render_enabled}:{settings.url_render_worker_url or ''}")
    policy_digest = hashlib.sha256(policy.encode("utf-8")).hexdigest()[:12]
    return f"{POLICY_VERSION}:{policy_digest}:{normalized_url}"


def _cached_link_response(cached: dict) -> dict:
    verdict = cached.get("verification_verdict")
    cached["risk_level"] = {
        "MALICIOUS": "High",
        "SUSPICIOUS": "Medium",
        "NO_THREAT_FOUND": "Low",
    }.get(verdict, "Unknown")
    cached["url_check"] = cached.get("url_check") or {}
    cached["policy_version"] = POLICY_VERSION
    cached["verification_route"] = (cached.get("checks") or {}).get("route", {}).get("status", "CORE_FAILURE")
    return cached


def _save_link_history(db_service, fraud_request: FraudCheckRequest, response: dict) -> None:
    url_check = response.get("url_check", {})
    db_service.save_history(
        user_id=fraud_request.user_id,
        message=fraud_request.message,
        classification=response.get("category"),
        is_fraud=response.get("is_fraud"),
        is_safe=response.get("is_safe"),
        confidence_score=response.get("confidence_score"),
        reason=response.get("reason_th"),
        url_check_result=url_check,
        has_malicious_urls=bool(url_check.get("malicious_urls")),
        model_used=response.get("model"),
        message_type=_resolve_history_message_type(fraud_request.message_type, url_check),
    )


def _save_complete_link_cache(db_service, fraud_request: FraudCheckRequest, response: dict, cache_key: str) -> None:
    url_check = response.get("url_check", {})
    ttl_seconds = (get_performance_config().URL_WEAK_RISK_TTL_SECONDS
                   if response.get("verification_verdict") in {"SUSPICIOUS", "MALICIOUS"} else 86400)
    for details in response.get("checks", {}).values():
        if expires := details.get("evidence_expires_at"):
            try:
                ttl_seconds = min(ttl_seconds, (datetime.fromisoformat(expires) - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError):
                return
    if ttl_seconds <= 0:
        return
    db_service.save_result(
        message=fraud_request.message,
        classification=response["category"],
        is_fraud=response["is_fraud"],
        is_safe=response["is_safe"],
        confidence_score=response.get("confidence_score"),
        reason=response.get("reason_th"),
        url_check_result=url_check,
        has_malicious_urls=bool(url_check.get("malicious_urls")),
        model_used=response.get("model"),
        cache_ttl_days=ttl_seconds / 86400,
        user_id=fraud_request.user_id,
        cache_key=cache_key,
        verification_verdict=response.get("verification_verdict"),
        verification_complete=True,
        checks=response.get("checks"),
        original_url=response.get("original_url"),
        final_url=response.get("final_url"),
        redirect_chain=response.get("redirect_chain"),
    )


async def _check_link_request(
    fraud_request: FraudCheckRequest,
    background_tasks: Optional[BackgroundTasks] = None,
    *, persist_history_before_return: bool = False,
    timeout: Optional[float] = None,
) -> dict:
    """Run the versioned URL-only pipeline and preserve history/cache contracts."""
    db_service = get_database_service()
    started = monotonic()
    config = get_performance_config()
    budget = min(config.MAX_TOTAL_PROCESSING_TIME, timeout) if timeout is not None else config.MAX_TOTAL_PROCESSING_TIME
    try:
        normalized = normalize_user_url(fraud_request.message)
    except URLSafetyError:
        normalized = fraud_request.message.strip()
    cache_key = _link_cache_key(normalized)
    cached = None
    if db_service:
        try:
            cached = await asyncio.wait_for(asyncio.to_thread(
                db_service.get_cached_result, fraud_request.message, cache_key=cache_key,
            ), timeout=config.DATABASE_OPERATION_TIMEOUT + 0.1)
        except Exception:
            cached = None
    risk_urls = [normalized]
    if cached and cached.get("final_url"):
        risk_urls.append(cached["final_url"])
    prior_risk = await lookup_recent_risk(db_service, risk_urls)
    if db_service:
        if (
            cached and cached.get("verification_complete") is True
            and cached.get("verification_verdict") in {"NO_THREAT_FOUND", "SUSPICIOUS", "MALICIOUS"}
            and (cached.get("url_check") or {}).get("policy_version") == POLICY_VERSION
            and (cached.get("verification_verdict") != "NO_THREAT_FOUND"
                 or prior_risk.get("status") == "not_listed")
        ):
            cached = _cached_link_response(cached)
            if background_tasks:
                background_tasks.add_task(db_service.record_url_cache_access, cache_key)
            else:
                remaining = budget - (monotonic() - started)
                if remaining > 0:
                    try:
                        await asyncio.wait_for(asyncio.to_thread(db_service.record_url_cache_access, cache_key), timeout=remaining)
                    except Exception:
                        logger.warning("url_cache_stats outcome=unavailable")
            if fraud_request.user_id:
                if background_tasks and not persist_history_before_return:
                    background_tasks.add_task(_save_link_history, db_service, fraud_request, cached)
                else:
                    await asyncio.to_thread(_save_link_history, db_service, fraud_request, cached)
            return cached

    response = await get_url_verification_service().verify(
        fraud_request.message, initial_risk=prior_risk,
        timeout=max(0.0, budget - (monotonic() - started)),
    )
    # Save positive evidence even when core is incomplete. Clean results never
    # write this store; do not depend on a background benign cache replacement.
    remaining = budget - (monotonic() - started)
    if remaining > 0:
        try:
            await asyncio.wait_for(save_recent_risk(db_service, response), timeout=remaining)
        except asyncio.TimeoutError:
            logger.warning("url_risk_save outcome=deadline")
            await save_recent_risk(db_service, response, persist=False)
    else:
        await save_recent_risk(db_service, response, persist=False)
    if db_service and fraud_request.user_id:
        if background_tasks and not persist_history_before_return:
            background_tasks.add_task(_save_link_history, db_service, fraud_request, response)
        else:
            await asyncio.to_thread(_save_link_history, db_service, fraud_request, response)

    if (db_service and response.get("verification_complete") and response.get("verification_verdict") != "INVALID"
            and response.get("checks", {}).get("risk_history", {}).get("status") != "suspicious"):
        if background_tasks:
            background_tasks.add_task(_save_complete_link_cache, db_service, fraud_request, response, cache_key)
        else:
            _save_complete_link_cache(db_service, fraud_request, response, cache_key)
    return response


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
async def check_fraud(request: Request, fraud_request: FraudCheckRequest, background_tasks: BackgroundTasks):
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
    # Public anonymous checking remains supported, but personal History may
    # only be written under a verified identity, never a supplied user_id.
    request_started = monotonic()
    if fraud_request.user_id or request.headers.get("Authorization"):
        user = await require_user(request.headers.get("Authorization", ""),
                                  request.headers.get("X-Auth-Provider", ""))
        fraud_request.user_id = user.user_id
    if fraud_request.message_type == "link":
        return await _check_link_request(fraud_request, background_tasks, timeout=max(
            0.0, get_performance_config().MAX_TOTAL_PROCESSING_TIME - (monotonic() - request_started)))

    try:
        # 1. Check database cache first
        db_service = get_database_service()
        cached_result = None

        if db_service:
            cached_result = db_service.get_cached_result(fraud_request.message)

            if cached_result:
                logger.info(f"Cache HIT for message (hash: {db_service.hash_message(fraud_request.message)[:8]}...)")

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
                        model_used=cached_result.get("model"),
                        message_type=_resolve_history_message_type(
                            fraud_request.message_type,
                            cached_result.get("url_check"),
                            cached_result.get("has_malicious_urls", False),
                        ),
                    )
                    logger.debug(f"Saved cache hit to history for user {fraud_request.user_id}")

                return cached_result

        logger.info(f"Cache MISS - checking with AI...")

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
        logger.debug(f"Starting parallel execution for message: {fraud_request.message[:20]}...")
        import time
        start_time = time.time()

        results = await asyncio.gather(ai_task, url_task if url_task else asyncio.sleep(0))

        result = results[0]
        url_check = results[1] if url_task else None

        if url_check is None and vt_service:
             url_check = {"error": "URL check skipped"}

        execution_time = time.time() - start_time
        logger.info(f"Parallel execution finished in {execution_time:.2f}s")

        # 5. Combine results
        response = {
            **result,
            "url_check": url_check,
            "cached": False,
            "execution_time": execution_time
        }

        # 6. Check and save adult websites from prescreen
        prescreen_service = get_prescreen_service()
        prescreen_result = prescreen_service.check_message(fraud_request.message, allow_network=False)

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
                                print(f"Saved adult website domain to blacklist: {domain} (confidence: 0.90)")
                        except Exception as url_error:
                            print(f"Failed to extract domain from {url}: {url_error}")
                except Exception as e:
                    print(f"Failed to save adult website domain: {e}")

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
                                print(f"Saved {category} domain to blacklist: {domain} (confidence: {confidence:.2f})")

                        except Exception as url_error:
                            print(f"Failed to extract domain from {url}: {url_error}")

                except Exception as e:
                    print(f"Failed to save malicious domain to blacklist: {e}")

        # 8. Save result to cache AND history
        if db_service:
            # Save to history log
            if fraud_request.user_id:
                try:
                    msg_type = _resolve_history_message_type(
                        fraud_request.message_type,
                        url_check,
                        has_malicious_urls,
                    )

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
                    logger.debug(f"Saved result to history for user {fraud_request.user_id}")
                except Exception as e:
                    logger.error(f"Failed to save history: {e}")

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
                logger.debug(f"Result saved to cache")
            except Exception as e:
                logger.error(f"Failed to save to cache: {e}")

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
                        logger.info(f"New fraud message saved (unique)")
                    else:
                        logger.debug(f"Fraud message updated (similarity: {save_result.get('similarity', 0):.2%}, hit_count incremented)")
                except Exception as e:
                    logger.error(f"Failed to save fraud message: {e}")

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
    try:
        return await get_url_verification_service().verify(url_request.message)
    except Exception as e:
        logger.error("URL check failed: %s", type(e).__name__)
        raise HTTPException(status_code=500, detail="URL check failed")
