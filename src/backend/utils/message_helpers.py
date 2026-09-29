"""Helper functions for message analysis and processing."""

import re
from typing import Optional


def is_analysis_request(message: str, quote_token: Optional[str] = None) -> bool:
    """
    Detect if user is requesting analysis (not just casual chat).

    Indicators:
    1. Message is just a URL (or URL with minimal text)
    2. Contains question keywords asking for analysis
    3. Quoted/forwarded message (quote_token exists)

    Args:
        message: User's message text
        quote_token: LINE quote token (exists if user quoted/forwarded message)

    Returns:
        True if user wants analysis, False if casual chat
    """
    message_clean = message.strip()

    # 1. Quoted/forwarded message = user wants analysis
    if quote_token:
        return True

    # 2. Message is mostly/only URL
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, message_clean)

    if urls:
        # Remove URLs from message
        message_without_urls = re.sub(url_pattern, '', message_clean).strip()

        # If message is just URL(s) with minimal text (< 20 chars)
        if len(message_without_urls) < 20:
            return True

    # 3. Contains question keywords asking for checking/analysis
    question_keywords = [
        'ปลอดภัย', 'ตรวจสอบ', 'เช็ค', 'check', 'ช่วยดู', 'ดูหน่อย',
        'โกงไหม', 'หลอกไหม', 'จริงไหม', 'ได้ไหม', 'เชื่อถือได้ไหม',
        'อันตราย', 'ระวัง', 'safe', 'scam', 'fraud', 'ไว้ใจได้ไหม'
    ]

    message_lower = message_clean.lower()
    for keyword in question_keywords:
        if keyword in message_lower:
            return True

    # 4. Very short message with URL = likely wants analysis
    if urls and len(message_clean) < 50:
        return True

    return False


def is_bot_mentioned(event: dict) -> bool:
    """
    Check if bot is mentioned in the message.
    
    LINE sends mention data in the message object when bot is tagged.
    Example: "@GunGong ช่วยเช็คข้อความนี้"
    
    Args:
        event: LINE webhook event object
    
    Returns:
        True if bot is mentioned, False otherwise
    """
    message = event.get("message", {})
    mention = message.get("mention")
    
    if mention and "mentionees" in mention:
        # Check if bot is in mentionees list
        for mentionee in mention["mentionees"]:
            if mentionee.get("type") == "bot":
                return True
    
    return False
