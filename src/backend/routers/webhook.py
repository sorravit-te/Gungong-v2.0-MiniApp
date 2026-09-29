"""LINE Webhook router for handling bot messages and events."""

import json
import re
import asyncio
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Header
from urllib.parse import parse_qs

from ..core.config import get_settings
from ..services.gemini_service import get_fraud_detector
from ..core.performance_config import (
    get_performance_config,
    should_skip_ai,
    should_skip_url_checks,
    should_do_full_check
)
from ..services.database_service import get_database_service
from ..services.line_service import get_line_service
from ..services.virustotal_service import get_virustotal_service
from ..services.fraud_message_service import get_fraud_message_service
from ..services.prescreen_service import get_prescreen_service
from ..services.feedback_service import get_feedback_service
from ..services.gambling_domain_service import get_gambling_domain_service
from ..services.id_card_service import get_id_card_service
from ..services.similarity_service import get_similarity_service
from ..services.image_classifier_service import get_image_classifier_service
from ..utils.message_helpers import is_analysis_request, is_bot_mentioned
from ..utils.flex_templates import create_id_card_verification_flex
from ..core.logger import get_logger

# Check LINE service availability
try:
    get_line_service()
    LINE_SERVICE_AVAILABLE = True
except (ImportError, SyntaxError):
    LINE_SERVICE_AVAILABLE = False

router = APIRouter()
logger = get_logger(__name__)
settings = get_settings()


@router.get("/webhook")
async def webhook_info():
    """
    GET endpoint for webhook - LINE uses this to verify the endpoint.

    LINE will send GET request to verify webhook URL is accessible.
    """
    return {
        "status": "ok",
        "message": "Webhook endpoint is ready. Use POST method to send events.",
        "endpoint": "/webhook",
        "method": "POST"
    }

@router.post("/webhook")
async def webhook(
    request: Request,
    x_line_signature: str = Header(None, alias="X-Line-Signature"),
):
    """
    LINE Webhook endpoint.

    This endpoint receives events from LINE Messaging API.

    Flow:
    1. User sends message to LINE Bot
    2. LINE sends webhook event here
    3. Extract message text
    4. Check with Gemini AI
    5. Reply to user with result
    """
    # Check if LINE service is available
    if not LINE_SERVICE_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="LINE service is not available (SDK compatibility issue with Python 3.13)"
        )
    # Get request body
    body = await request.body()
    body_str = body.decode("utf-8")

    # Verify LINE signature (optional but recommended)
    if settings.line_channel_secret and x_line_signature:
        try:
            line_service = get_line_service()
            # Note: Full signature verification requires parsing events
            # For now, we'll proceed if credentials exist
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid signature: {str(e)}")

    # Parse webhook body
    try:
        webhook_data = json.loads(body_str)
        events = webhook_data.get("events", [])
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Process each event
    for event in events:
        reply_token = event.get("replyToken")
        source = event.get("source", {})
        
        if not reply_token:
            continue

        # Handle Postback events (Feedback buttons)
        if event.get("type") == "postback":
            postback_data = event["postback"].get("data")
            user_id = source.get("userId")
            
            print(f"📩 Postback received: {postback_data} from {user_id}")
            
            if postback_data and user_id:
                feedback_service = get_feedback_service()
                if feedback_service:
                    success = feedback_service.save_feedback_from_postback(postback_data, user_id)
                    
                    if success:
                        # Reply to acknowledge feedback
                        # We parse the feedback type to give a specific response
                        from urllib.parse import parse_qs
                        parsed = parse_qs(postback_data)
                        feedback_type = parsed.get("feedback", [""])[0]
                        
                        reply_text = "ขอบคุณสำหรับข้อมูลครับ! 🙏"
                        if "incorrect" in feedback_type:
                            reply_text = "ขอบคุณครับ! ระบบได้แก้ไขข้อมูลตามที่คุณแจ้งแล้ว ✅"
                        elif "correct" in feedback_type:
                            reply_text = "ขอบคุณที่ช่วยยืนยันความถูกต้องครับ! 👍"
                            
                        line_service = get_line_service()
                        line_service.reply_message(reply_token, text=reply_text)
            continue

        # Handle Text messages
        if event.get("type") == "message" and event["message"].get("type") == "text":
            message_text = event["message"].get("text", "")
            quote_token = event["message"].get("quoteToken")  # Extract quote token

            # Detect message source (group vs 1-on-1)
            source_type = source.get("type", "user")  # "user", "group", or "room"
            is_group = source_type in ["group", "room"]

            if not message_text:
                continue

            try:
                # Get services
                prescreen_service = get_prescreen_service()
                line_service = get_line_service()
                db_service = get_database_service()
                fraud_message_service = get_fraud_message_service()

                # --- HACKATHON MODE: Instant Feedback Learning ---
                # This logic allows for immediate learning from user feedback, ideal for demos.
                # For production, a human-in-the-loop system is recommended to prevent system poisoning.
                feedback_commands = {"#f", "#ผิด", "#wrong"}
                command_found = None
                
                # Use a regex to find commands to avoid partial matches in words
                for command in feedback_commands:
                    if re.search(r'\b' + re.escape(command) + r'\b', message_text.lower()):
                        command_found = command
                        break

                if command_found and fraud_message_service:
                    print(f"⚡️ Hackathon Feedback received: '{command_found}'")
                    # This is a feedback message. Learn from it and stop.
                    # Remove the command to get the clean message
                    fraud_text = re.sub(r'\b' + re.escape(command_found) + r'\b', '', message_text, flags=re.IGNORECASE).strip()

                    if fraud_text:
                        # Save this as a high-confidence fraud message
                        save_result = fraud_message_service.save_fraud_message(
                            message_text=fraud_text,
                            category="USER_REPORTED_FRAUD",
                            confidence_score=0.99, # User-confirmed fraud
                            keywords=["user_feedback", command_found]
                        )

                        if save_result.get("saved"):
                            reply_text = "✅ ขอบคุณสำหรับ Feedback ครับ! ระบบได้เรียนรู้และบันทึกข้อมูลนี้เรียบร้อยแล้ว"
                        else:
                            reply_text = "✅ ขอบคุณสำหรับ Feedback ครับ! ข้อความนี้มีอยู่ในระบบแล้ว เราจะนำข้อมูลไปปรับปรุงต่อไป"
                    else:
                        reply_text = "⚠️ ไม่พบข้อความให้บันทึก กรุณาส่งต่อ (Forward) ข้อความที่ต้องการรายงานแล้วพิมพ์ #ผิด หรือ #f ต่อท้ายครับ"

                    # Reply to user and stop processing for this event
                    line_service.reply_message(reply_token, text=reply_text)
                    continue # Skip to the next event
                # --- End of Hackathon Mode ---

                # Get performance config
                perf_config = get_performance_config()

                # Step 1: Pre-screen message (fast, rule-based)
                # This also expands URLs and scrapes content for a more accurate analysis
                prescreen_result = prescreen_service.check_message(message_text)
                prescreen_confidence = prescreen_result.confidence
                
                # Use the processed message for all downstream analysis
                analysis_message = prescreen_result.analysis_message
                # 2. Calculate message hash for feedback tracking
                message_hash = db_service.hash_message(analysis_message) if db_service else None

                # Detect if user is requesting analysis
                user_wants_analysis = is_analysis_request(message_text, quote_token)

                # Different behavior for group vs personal chat
                # Group: Only respond if bot is mentioned (opt-in model)
                # Personal: Always respond/check to ensure history logging
                user_id = source.get("userId")
                
                # Get proper target ID for reply (Group/Room/User)
                source_type = source.get("type", "user")
                if source_type == "group":
                    target_id = source.get("groupId")
                elif source_type == "room":
                    target_id = source.get("roomId")
                else:
                    target_id = user_id
                
                if is_group:
                    # Group: Only process if bot is mentioned
                    bot_mentioned = is_bot_mentioned(event)
                    should_respond = bot_mentioned
                    
                    # Logging behavior
                    if bot_mentioned:
                        print(f"Pre-screen result: source=GROUP/ROOM, "
                              f"bot_mentioned=YES, "
                              f"confidence={prescreen_confidence:.2f}, "
                              f"will_respond=YES (bot mentioned), "
                              f"patterns={prescreen_result.matched_patterns}")
                    else:
                        print(f"Pre-screen result: source=GROUP/ROOM, "
                              f"bot_mentioned=NO, "
                              f"confidence={prescreen_confidence:.2f}, "
                              f"will_respond=NO (bot not mentioned - silent), "
                              f"patterns={prescreen_result.matched_patterns}")
                        # Skip processing entirely if bot is not mentioned in group
                        continue
                else:
                    # Personal chat: Always respond
                    should_respond = True
                    analysis_reason = ""
                    if user_wants_analysis:
                        analysis_reason = " (user requested analysis)"
                    print(f"Pre-screen result: source=PERSONAL, "
                          f"confidence={prescreen_confidence:.2f}, "
                          f"user_wants_analysis={user_wants_analysis}, "
                          f"will_respond={should_respond}{analysis_reason}, "
                          f"patterns={prescreen_result.matched_patterns}")
                
                print(f"DEBUG: Webhook - user_id={user_id}, target_id={target_id}, source_type={source_type}, should_respond={should_respond}")

                # Determine routing strategy based on pre-screen confidence
                # If user explicitly requested analysis, always do full check
                if user_wants_analysis and prescreen_confidence < 0.5:
                    print(f"🔍 USER REQUEST: User requested analysis, performing full check")
                    routing_strategy = "full"
                elif should_skip_ai(prescreen_confidence):
                    print(f"🚀 FAST PATH: Pre-screen confidence {prescreen_confidence:.2%} >= {perf_config.PRESCREEN_INSTANT_THRESHOLD:.2%} - skipping AI, instant response")
                    routing_strategy = "instant"
                elif should_skip_url_checks(prescreen_confidence):
                    print(f"⚡ AI ONLY: Pre-screen confidence {prescreen_confidence:.2%} >= {perf_config.PRESCREEN_AI_ONLY_THRESHOLD:.2%} - using AI only, skipping URL checks")
                    routing_strategy = "ai_only"
                elif should_do_full_check(prescreen_confidence):
                    print(f"🔍 FULL CHECK: Pre-screen confidence {prescreen_confidence:.2%} < {perf_config.PRESCREEN_FULL_CHECK_THRESHOLD:.2%} - performing full check")
                    routing_strategy = "full"
                else:
                    routing_strategy = "full"  # Default to full check

                # Step 2: Run fraud detection for ALL messages (not just when should_respond=True)
                # This ensures all messages are logged to history
                # Actual response sending is conditional later based on is_fraud
                
                # Step 2.1: Check database cache first
                cached_result = None
                url_check = None
                similarity_data = None

                if db_service:
                    cached_result = db_service.get_cached_result(analysis_message)

                    if cached_result:
                        print(f"✅ Cache HIT - using cached result for: {analysis_message[:100]}...")
                        # Use cached_result directly
                        result = cached_result
                        url_check = cached_result.get("url_check")

                # Step 2.2: If cache miss, use AI for detailed analysis
                if not cached_result:
                    # The original message_text is passed to save_result later
                    print(f"⚠️  Cache MISS - checking with AI for: {analysis_message[:100]}...")

                    # Handle INSTANT routing (skip AI entirely)
                    if routing_strategy == "instant":
                        # Pattern-based response only
                        result = {
                            "category": "FRAUD_GAMBLING_AD",  # Inferred from patterns
                            "is_fraud": True,
                            "is_safe": False,
                            "confidence_score": prescreen_confidence,
                            "reason_th": f"ตรวจพบรูปแบบการฉ้อโกงจากการวิเคราะห์เบื้องต้น: {', '.join(prescreen_result.matched_patterns[:3])}",
                            "keywords_found": prescreen_result.matched_patterns,
                            "model": "pattern_matching",
                            "risk_level": "High",
                            "message_length": len(analysis_message)
                        }
                        print(f"🚀 Instant response (pattern-based): {result['category']}, confidence: {prescreen_confidence:.2%}")

                    else:
                        # AI-based or full check
                        detector = get_fraud_detector()
                        vt_service = get_virustotal_service()

                        # Run AI classification and URL check in PARALLEL using asyncio with TIMEOUT
                        async def parallel_checks():
                            """Run AI and URL checks concurrently with timeout."""
                            tasks = []

                            # Task 1: AI classification (Context-Aware)
                            if prescreen_result.is_educational_context:
                                print("🧠 Using educational prompt for AI analysis.")
                                ai_task = asyncio.create_task(detector.classify_educational_with_details_async(analysis_message))
                            else:
                                ai_task = asyncio.create_task(detector.classify_with_details_async(analysis_message))
                            tasks.append(ai_task)

                            # Task 2: URL check (only for FULL routing, skip for AI_ONLY)
                            if vt_service and routing_strategy == "full":
                                url_task = asyncio.create_task(vt_service.check_text_for_malicious_urls_async(analysis_message))
                                tasks.append(url_task)

                            # Wait for all tasks with global timeout
                            try:
                                return await asyncio.wait_for(
                                    asyncio.gather(*tasks, return_exceptions=True),
                                    timeout=perf_config.MAX_TOTAL_PROCESSING_TIME
                                )
                            except asyncio.TimeoutError:
                                print(f"⏱️ Global timeout ({perf_config.MAX_TOTAL_PROCESSING_TIME}s) exceeded, using partial results")
                                # Return partial results safely
                                results = []
                                for task in tasks:
                                    if task.done() and not task.cancelled():
                                        try:
                                            results.append(task.result())
                                        except Exception as e:
                                            print(f"⚠️ Task failed: {e}")
                                            results.append(None)
                                    else:
                                        results.append(None)
                                return results

                        # Execute parallel checks and handle partial failures
                        try:
                            parallel_results = await parallel_checks()
                            
                            ai_result = parallel_results[0] if parallel_results else None
                            url_check = parallel_results[1] if len(parallel_results) > 1 and routing_strategy == "full" else None

                            # Check for URL check success first
                            if url_check and not isinstance(url_check, Exception) and url_check.get("is_dangerous"):
                                print("✅ VirusTotal check SUCCEEDED and found a malicious URL.")
                                # If AI failed, create a result based on the VT finding
                                if ai_result is None or isinstance(ai_result, Exception):
                                    print(f"⚠️ AI check failed or timed out: {ai_result}. Creating result from successful URL check.")
                                    result = {
                                        "category": "SCAM_MALICIOUS",
                                        "risk_level": "High",
                                        "is_fraud": True,
                                        "is_safe": False,
                                        "confidence_score": 95,
                                        "reason_th": "ตรวจพบ URL ที่เป็นอันตรายสูงจากระบบสแกนไวรัส",
                                        "keywords_found": ["malicious_url"],
                                        "model": "virustotal_fallback",
                                        "message_length": len(analysis_message)
                                    }
                                else:
                                    # AI succeeded, use its result but ensure it's marked as fraud
                                    result = ai_result
                                    result["is_fraud"] = True 
                            else:
                                # URL check either failed, didn't run, or found nothing dangerous
                                if isinstance(url_check, Exception):
                                    print(f"⚠️ VirusTotal check failed: {url_check}")
                                    url_check = None
                                
                                # Now, handle AI result
                                if ai_result is None or isinstance(ai_result, Exception):
                                    print(f"⚠️ AI check failed and URL check was inconclusive. Falling back to pattern-based result. AI Error: {ai_result}")
                                    result = {
                                        "category": "FRAUD_GAMBLING_AD" if prescreen_confidence >= 0.5 else "SAFE_NORMAL",
                                        "is_fraud": prescreen_confidence >= 0.5,
                                        "is_safe": prescreen_confidence < 0.5,
                                        "confidence_score": prescreen_confidence,
                                        "reason_th": "ระบบประมวลผล AI ขัดข้อง, ใช้ผลการวิเคราะห์เบื้องต้น",
                                        "keywords_found": prescreen_result.matched_patterns,
                                        "model": "pattern_fallback",
                                        "risk_level": "Medium" if prescreen_confidence >= 0.5 else "Low",
                                        "message_length": len(analysis_message)
                                    }
                                else:
                                    result = ai_result

                        except Exception as e:
                            # Fallback for the entire parallel execution block
                            print(f"⚠️  Parallel execution failed entirely, falling back to sequential: {e}")
                            result = {
                                "category": "FRAUD_GAMBLING_AD" if prescreen_confidence >= 0.5 else "SAFE_NORMAL",
                                "is_fraud": prescreen_confidence >= 0.5,
                                "is_safe": prescreen_confidence < 0.5,
                                "confidence_score": prescreen_confidence,
                                "reason_th": "ระบบขัดข้อง, ใช้ผลการวิเคราะห์เบื้องต้น",
                                "keywords_found": prescreen_result.matched_patterns,
                                "model": "pattern_fallback",
                                "risk_level": "Medium",
                                "message_length": len(analysis_message)
                            }
                            url_check = None
                            try:
                                if vt_service and routing_strategy == "full":
                                    url_check = vt_service.check_text_for_malicious_urls(analysis_message)
                            except Exception as vt_e:
                                print(f"⚠️  VirusTotal fallback check also failed: {vt_e}")
                                url_check = None

                    # Step 3.1: Save malicious/gambling domains to blacklist (if URL is dangerous)
                    # Check whitelist first!
                    if url_check and url_check.get("is_dangerous", False):
                        from .services.gambling_domain_service import get_gambling_domain_service
                        gambling_service = get_gambling_domain_service()
                        
                        if gambling_service:
                            # Filter out whitelisted domains
                            from urllib.parse import urlparse
                            
                            # Filter malicious_urls
                            new_malicious_urls = []
                            for url in url_check.get("malicious_urls", []):
                                try:
                                    parsed = urlparse(url)
                                    domain = parsed.netloc or parsed.path.split('/')[0]
                                    if domain and gambling_service.is_whitelisted(domain):
                                        print(f"🛡️ Ignoring whitelisted domain: {domain}")
                                        continue
                                    new_malicious_urls.append(url)
                                except:
                                    new_malicious_urls.append(url)
                            
                            url_check["malicious_urls"] = new_malicious_urls
                            
                            # Filter gambling_urls
                            new_gambling_urls = []
                            for url in url_check.get("gambling_urls", []):
                                try:
                                    parsed = urlparse(url)
                                    domain = parsed.netloc or parsed.path.split('/')[0]
                                    if domain and gambling_service.is_whitelisted(domain):
                                        print(f"🛡️ Ignoring whitelisted domain: {domain}")
                                        continue
                                    new_gambling_urls.append(url)
                                except:
                                    new_gambling_urls.append(url)
                                    
                            url_check["gambling_urls"] = new_gambling_urls
                            
                            # Re-evaluate is_dangerous
                            url_check["is_dangerous"] = bool(new_malicious_urls or new_gambling_urls)
                            if not url_check["is_dangerous"]:
                                print("✅ All dangerous URLs were whitelisted. Marking as safe.")

                    has_malicious_urls = url_check and url_check.get("is_dangerous", False)
                    if has_malicious_urls and db_service:
                        try:
                            from urllib.parse import urlparse

                            # Collect all dangerous URLs (malicious + gambling)
                            dangerous_urls = url_check.get("malicious_urls", []) + url_check.get("gambling_urls", [])

                            for url in dangerous_urls:
                                try:
                                    # Extract domain from URL
                                    parsed = urlparse(url)
                                    domain = parsed.netloc or parsed.path.split('/')[0]

                                    if domain:
                                        # Determine confidence based on type
                                        is_malicious = url in url_check.get("malicious_urls", [])
                                        is_gambling = url in url_check.get("gambling_urls", [])

                                        if is_malicious:
                                            # Get VirusTotal confidence from details
                                            confidence = 1.0  # Default high confidence for malicious
                                            category = "malicious_url"
                                            source = "virustotal"

                                            # Try to get actual detection ratio
                                            for detail in url_check.get("details", []):
                                                if detail["url"] == url and "/" in detail.get("detections", ""):
                                                    parts = detail["detections"].split("/")
                                                    if len(parts) == 2 and parts[1].isdigit():
                                                        malicious_count = int(parts[0])
                                                        total_engines = int(parts[1])
                                                        if total_engines > 0:
                                                            confidence = min(1.0, malicious_count / total_engines)

                                        elif is_gambling:
                                            # Get gambling confidence from details
                                            confidence = 0.8  # Default confidence for gambling
                                            category = "gambling"
                                            source = "gambling_detector"

                                            for detail in url_check.get("details", []):
                                                if detail["url"] == url:
                                                    confidence = detail.get("gambling_confidence", 0.8)

                                        # Save to blacklist
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

                    # Step 3.2: Save to cache ONLY if fraud detected (to save database space)
                    if db_service and result["is_fraud"]:
                        try:
                            db_service.save_result(
                                message=message_text,
                                classification=result["category"],  # Use new 'category' field
                                is_fraud=result["is_fraud"],
                                is_safe=result["is_safe"],
                                confidence_score=result.get("confidence_score"),
                                reason=result.get("reason_th"),  # Use Thai reason
                                url_check_result=url_check,
                                has_malicious_urls=has_malicious_urls,
                                model_used=result.get("model"),
                                cache_ttl_days=30
                            )
                            print(f"💾 Fraud result saved to cache")
                        except Exception as e:
                            print(f"⚠️  Failed to save to cache: {e}")

                    # Step 3.2: Save to fraud_messages table (if fraud detected, with deduplication)
                    if result["is_fraud"]:
                        fraud_service = get_fraud_message_service()
                        if fraud_service:
                            try:
                                # Combine keywords from AI, prescreen patterns, and expanded URLs
                                ai_keywords = result.get("keywords_found", [])
                                pattern_keywords = prescreen_result.matched_patterns
                                
                                # prescreen_result.urls_found is already a list of final, expanded URL strings
                                url_keywords = prescreen_result.urls_found

                                # Ensure all keywords are unique, non-empty strings
                                combined_keywords = set(ai_keywords + pattern_keywords + url_keywords)
                                final_keywords = [str(kw) for kw in combined_keywords if kw]

                                save_result = fraud_service.save_fraud_message(
                                    message_text=analysis_message,
                                    category=result["category"],
                                    confidence_score=result.get("confidence_score"),
                                    keywords=final_keywords
                                )
                                if save_result["saved"]:
                                    print(f"💾 New fraud message saved (unique)")
                                else:
                                    print(f"💾 Fraud message updated (similarity: {save_result.get('similarity', 0):.2%}, hit_count incremented)")
                            except Exception as e:
                                print(f"⚠️  Failed to save fraud message: {e}")

                    # Step 3.3: Auto-save gambling domains detected in URLs
                    if url_check and url_check.get("gambling_urls"):
                        from .services.gambling_domain_service import get_gambling_domain_service
                        domain_service = get_gambling_domain_service()

                        for url_data in url_check.get("results", []):
                            if url_data.get("is_gambling") and url_data.get("gambling_confidence", 0) >= 0.7:
                                try:
                                    # Extract domain from URL
                                    from urllib.parse import urlparse
                                    domain = urlparse(url_data["url"]).netloc

                                    # Save to database
                                    domain_service.add_or_update_domain(
                                        domain=domain,
                                        confidence=url_data["gambling_confidence"],
                                        category="gambling",
                                        source="content_analysis",
                                        keywords=url_data.get("gambling_keywords", [])
                                    )
                                except Exception as e:
                                    print(f"⚠️  Failed to save gambling domain: {e}")

                # Step 4: Calculate similarity analysis (ALWAYS, not just for fraud)
                # This provides danger_percentage for Flex Message
                similarity_service = get_similarity_service()
                if similarity_service and result.get("is_fraud"):
                    # Only run similarity for fraud messages (to save time)
                    try:
                        # Use batched analysis to get both frequency and danger score
                        # This loads fraud DB only once instead of twice
                        similarity_data = similarity_service.get_message_analysis(analysis_message)

                        frequency = similarity_data["frequency"]
                        danger_analysis = similarity_data["danger_analysis"]

                        print(f"📊 Similarity: {danger_analysis.get('danger_percentage', 0):.1f}%, seen {frequency.get('times_seen', 0)} times")
                    except Exception as e:
                        print(f"⚠️  Similarity analysis failed: {e}")

                # If no similarity data, use pre-screen confidence as danger percentage
                if not similarity_data or not similarity_data.get("danger_analysis"):
                    # Convert pre-screen confidence (0-1) to danger percentage (0-100)
                    danger_pct = prescreen_confidence * 100
                    similarity_data = {
                        "danger_analysis": {
                            "danger_percentage": danger_pct,
                            "source": "prescreen"
                        },
                        "frequency": {
                            "times_seen": 1,
                            "seen_before": False
                        }
                    }
                    print(f"📊 Using pre-screen confidence as danger: {danger_pct:.1f}%")

                # Step 5: Save to history log (for both Personal and Group/Room messages)
                # For Group/Room: use target_id (group_id or room_id)
                # For Personal: use user_id
                save_user_id = user_id if user_id else target_id  # Fallback to target_id for groups
                history_id = None
                if db_service and save_user_id:
                    try:
                        history_id = db_service.save_history(
                            user_id=save_user_id,  # Can be user_id, group_id, or room_id
                            message=message_text, # Use original message text
                            classification=result.get("category"),
                            is_fraud=result.get("is_fraud"),
                            is_safe=result.get("is_safe"),
                            confidence_score=result.get("confidence_score"),
                            reason=result.get("reason_th"),
                            reasoning_summary=result.get("reasoning_summary"),
                            url_check_result=url_check,
                            has_malicious_urls=has_malicious_urls,
                            model_used=result.get("model"),
                            message_type="link" if (has_malicious_urls or url_check) else "message"
                        )
                        source_label = "GROUP/ROOM" if is_group else "USER"
                        print(f"📜 Saved {source_label} message to history for {save_user_id} (ID: {history_id})")
                    except Exception as e:
                        print(f"⚠️  Failed to save history: {e}")

                # Step 6: Create and send response ONLY for dangerous messages OR when explicitly requested
                # Safe messages are logged but not sent to avoid annoying users
                is_fraud = result.get("is_fraud", False)
                
                if (is_fraud and should_respond) or user_wants_analysis:
                    # Option 1: Use Flex Message (prettier, more informative)
                    print("🎨 Creating Flex Message response for DANGEROUS message...")
                    flex_message = line_service.create_fraud_flex_message(
                        classification=result["category"],
                        is_fraud=result["is_fraud"],
                        confidence_score=result.get("confidence_score"),
                        url_check=url_check,
                        message_hash=message_hash,
                        similarity_data=similarity_data,
                        history_id=history_id
                    )
                    print(f"🎨 Flex message created: {flex_message.get('alt_text', 'N/A')}")
                    print(f"🎨 Sending reply with reply_token={reply_token[:20]}..., quote_token={quote_token[:20] if quote_token else None}...")
                    line_service.reply_message(reply_token, flex_message=flex_message, quote_token=quote_token)
                    print(f"🎨 Reply sent!")
                    print(f"AI check completed: {result['category']}")
                else:
                    print(f"✅ Message checked (is_fraud={is_fraud}, should_respond={should_respond}) - NOT sending response (silent mode)")
                    print(f"AI check completed: {result['category']}")

            except Exception as e:
                # Log error but don't crash
                print(f"Error processing message: {str(e)}")

                # Try to send error message to user
                try:
                    line_service = get_line_service()
                    line_service.reply_message(
                        reply_token,
                        "ขออภัย เกิดข้อผิดพลาดในการตรวจสอบข้อความ กรุณาลองใหม่อีกครั้ง"
                    )
                except:
                    pass

        # --- 2. Handle Image Messages (Smart Image Analysis) ---
        elif event.get("type") == "message" and event["message"].get("type") == "image":
            message_id = event["message"].get("id")
            user_id = source.get("userId")

            if not message_id:
                continue

            print(f"📸 Received image from user: {user_id}")

            try:
                line_service = get_line_service()
                classifier_service = get_image_classifier_service()
                id_card_service = get_id_card_service()

                # Import LINE SDK components for image download
                from linebot.v3.messaging import MessagingApi, MessagingApiBlob, ApiClient

                # Download image from LINE
                with ApiClient(line_service.configuration) as api_client:
                    line_bot_blob_api = MessagingApiBlob(api_client)

                    # Get image binary content
                    image_content = line_bot_blob_api.get_message_content(message_id)

                    # Convert to base64
                    import base64
                    image_base64 = base64.b64encode(image_content).decode('utf-8')

                    print(f"[OK] Image downloaded, size: {len(image_content)} bytes")

                    # Step 1: Classify image type
                    print("[CLASSIFY] Classifying image type...")
                    classification = classifier_service.classify_image(image_base64)

                    image_type = classification.get("image_type", "general")
                    confidence = classification.get("confidence", 0)

                    print(f"[CLASSIFY] Type: {image_type}, Confidence: {confidence:.2f}")

                    # Step 2: Handle based on image type
                    if image_type == "general":
                        # General image (photos, animals, people, etc.) - No response
                        print(f"[SKIP] General image detected, no action needed")
                        continue

                    elif image_type == "qr_code":
                        # QR Code detected - Check if dangerous
                        print("[QR] QR Code detected, checking URL...")
                        qr_url = classification.get("qr_url")

                        if not qr_url:
                            line_service.reply_message(
                                reply_token,
                                text="🔍 พบ QR Code แต่ไม่สามารถอ่านข้อมูลได้\nกรุณาถ่ายรูปให้ชัดเจนขึ้น"
                            )
                            continue

                        # Check URL safety using fraud detection
                        print(f"[QR] Checking URL: {qr_url}")
                        fraud_detector = get_fraud_detector()
                        fraud_result = fraud_detector.check_message(qr_url)

                        is_fraud = fraud_result.get("is_fraud", False)
                        category = fraud_result.get("category", "SAFE_NORMAL")
                        confidence_score = fraud_result.get("confidence_score", 0)

                        if is_fraud:
                            # Dangerous QR Code
                            risk_emoji = "🚨" if confidence_score >= 80 else "⚠️"
                            line_service.reply_message(
                                reply_token,
                                text=f"{risk_emoji} **ระวัง! QR Code อันตราย**\n\n"
                                     f"URL: {qr_url}\n\n"
                                     f"ประเภท: {fraud_result.get('reason_th', 'อันตราย')}\n"
                                     f"ความมั่นใจ: {confidence_score}%\n\n"
                                     f"⚠️ **อย่าสแกนหรือเปิดลิงก์นี้!**"
                            )
                        else:
                            # Safe QR Code
                            line_service.reply_message(
                                reply_token,
                                text=f"✅ QR Code ปลอดภัย\n\n"
                                     f"URL: {qr_url}\n\n"
                                     f"ไม่พบความเสี่ยง"
                            )
                        continue

                    elif image_type == "id_card":
                        # ID Card detected - Verify
                        print("[ID CARD] ID card detected, verifying...")
                        result = id_card_service.verify_id_card(image_base64)

                        if not result.get("success"):
                            error_msg = result.get("error", "Unknown error")
                            print(f"[ERROR] ID card verification failed: {error_msg}")
                            line_service.reply_message(
                                reply_token,
                                text=f"❌ ไม่สามารถอ่านบัตรประชาชนได้\n\n"
                                     f"กรุณาถ่ายรูปให้ชัดเจนและแสงสว่างเพียงพอ\n"
                                     f"ตรวจสอบว่าบัตรอยู่ในกรอบทั้งหมด"
                            )
                            continue

                        # Extract data
                        extracted_data = result.get("extracted_data", {})
                        id_number = result.get("id_number", "-")
                        name_th = extracted_data.get("name_th", "")
                        surname_th = extracted_data.get("surname_th", "")
                        date_of_birth = extracted_data.get("date_of_birth", "-")
                        address = extracted_data.get("address", "-")

                        is_blacklisted = result.get("is_blacklisted", False)
                        is_valid_format = result.get("is_valid_format", False)
                        risk_level = result.get("risk_level", "LOW")
                        reports_count = result.get("reports_count", 0)

                        # Determine status icon and message
                        if is_blacklisted:
                            icon = "⚠️"
                            status = "พบในบัญชีดำ"
                            safety = "ไม่ปลอดภัย"
                            warning_msg = f"• ระวัง! เลขบัตรนี้มี {reports_count} รายงานการฉ้อโกง"
                        elif not is_valid_format:
                            icon = "⚠️"
                            status = "รูปแบบไม่ถูกต้อง"
                            safety = "ควรตรวจสอบ"
                            warning_msg = "• เลขบัตรไม่ผ่านการตรวจสอบ checksum"
                        else:
                            icon = "✅"
                            status = "ปลอดภัย"
                            safety = "ปลอดภัย"
                            warning_msg = "• ไม่พบข้อมูลในบัญชีดำ"

                        # Build Flex Message response
                        try:
                            print("[FLEX] Creating Flex Message...")
                            flex_message_obj = create_id_card_verification_flex(
                                id_number=id_number,
                                name_th=name_th,
                                surname_th=surname_th,
                                date_of_birth=date_of_birth,
                                address=address,
                                is_blacklisted=is_blacklisted,
                                is_valid_format=is_valid_format,
                                risk_level=risk_level,
                                reports_count=reports_count
                            )

                            print(f"[OK] ID card verified: {id_number[:4]}****{id_number[-2:]}, "
                                  f"blacklisted: {is_blacklisted}, risk: {risk_level}")

                            # Convert FlexMessage to dict for reply_message
                            flex_message_dict = {
                                "alt_text": flex_message_obj.alt_text,
                                "contents": flex_message_obj.contents.to_dict()
                            }

                            print("[FLEX] Sending Flex Message...")
                            # Reply to user with Flex Message
                            line_service.reply_message(reply_token, flex_message=flex_message_dict)
                            print("[FLEX] Flex Message sent successfully!")
                        except Exception as flex_error:
                            print(f"[ERROR] Flex Message creation failed: {flex_error}")
                            import traceback
                            traceback.print_exc()

                            # Fallback to text message
                            fallback_text = f"""
{icon} ผลการตรวจสอบบัตรประชาชน

ข้อมูลบัตร:
• เลขบัตร: {id_number}
• ชื่อ-นามสกุล: {name_th} {surname_th}
• วันเกิด: {date_of_birth}

ผลการตรวจสอบ:
• สถานะ: {status}
• ระดับความเสี่ยง: {risk_level}
• จำนวนรายงาน: {reports_count} ครั้ง
                            """.strip()
                            line_service.reply_message(reply_token, text=fallback_text)

            except Exception as e:
                print(f"[ERROR] Image processing error: {e}")
                import traceback
                traceback.print_exc()

                try:
                    line_service = get_line_service()
                    line_service.reply_message(
                        reply_token,
                        text="[X] เกิดข้อผิดพลาดในการประมวลผลรูปภาพ\n\n"
                             "กรุณาลองใหม่อีกครั้ง หรือถ่ายรูปให้ชัดเจนกว่านี้"
                    )
                except:
                    pass
            continue

        # --- 3. Handle Postback Events for Feedback ---
        elif event.get("type") == "postback":
            postback_data = event["postback"].get("data")
            user_id = event["source"].get("userId")

            if postback_data and user_id:
                # Check if this is a feedback action
                if "action=feedback" in postback_data:
                    print(f"👍 Received feedback postback from user {user_id}")
                    try:
                        feedback_service = get_feedback_service()
                        if feedback_service:
                            feedback_service.save_feedback_from_postback(postback_data, user_id)
                        # No reply needed as button press has displayText
                    except Exception as e:
                        print(f"❌ Failed to save feedback: {e}")

    return {"status": "ok"}


# Note: Global exception handlers should be defined in main.py, not in routers
# @app.exception_handler(Exception)
# async def global_exception_handler(request: Request, exc: Exception):
#     """Global exception handler."""
#     return JSONResponse(
#         status_code=500,
#         content={"detail": f"Internal server error: {str(exc)}"}
#     )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug,
    )