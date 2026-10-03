"""LINE Bot service for sending messages and handling webhooks."""

import asyncio
import re
import httpx
from linebot.v3 import WebhookHandler
from linebot.v3.messaging import (
    Configuration,
    ApiClient,
    MessagingApi,
    ReplyMessageRequest,
    TextMessage,
    FlexMessage,
    FlexContainer,
    FlexBubble,
    FlexBox,
    FlexText,
    FlexSeparator,
)
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.webhooks import MessageEvent, TextMessageContent
from typing import Optional
from ..core.config import settings
from ..core.logger import get_logger
from ..utils.result_presentation import resolve_result_verdict


logger = get_logger(__name__)
LINE_LOADING_REQUEST_TIMEOUT_SECONDS = 2.0

def _miniapp_history_uri(history_id=None):
    uri = "https://miniapp.line.me/2008548759-KkM4Noxa?section=history"
    if isinstance(history_id, str) and re.fullmatch(r"[A-Za-z0-9_-]{1,128}", history_id):
        uri += f"&historyId={history_id}"
    return uri


class LineService:
    """Service for handling LINE Bot operations."""

    def __init__(
        self,
        channel_access_token: Optional[str] = None,
        channel_secret: Optional[str] = None,
    ):
        """
        Initialize LINE service.

        Args:
            channel_access_token: LINE channel access token. If None, uses settings.
            channel_secret: LINE channel secret. If None, uses settings.
        """
        self.channel_access_token = channel_access_token or settings.line_channel_access_token
        self.channel_secret = channel_secret or settings.line_channel_secret

        if not self.channel_access_token:
            raise ValueError("LINE_CHANNEL_ACCESS_TOKEN not found")
        if not self.channel_secret:
            raise ValueError("LINE_CHANNEL_SECRET not found")

        # Initialize LINE Bot SDK
        self.configuration = Configuration(access_token=self.channel_access_token)
        self.handler = WebhookHandler(self.channel_secret)

    async def show_loading_animation(self, user_id: str, loading_seconds: int = 30) -> bool:
        """Best-effort native chat loading; never send or consume a reply message."""
        if not isinstance(user_id, str) or not re.fullmatch(r"U[0-9a-f]{32}", user_id):
            return False
        if type(loading_seconds) is not int or loading_seconds not in range(5, 61, 5):
            return False
        try:
            # Bound the entire request, not just each network phase. No retries or redirects.
            async with asyncio.timeout(LINE_LOADING_REQUEST_TIMEOUT_SECONDS):
                async with httpx.AsyncClient(
                    timeout=LINE_LOADING_REQUEST_TIMEOUT_SECONDS,
                    follow_redirects=False, trust_env=False,
                ) as client:
                    response = await client.post(
                        "https://api.line.me/v2/bot/chat/loading/start",
                        headers={"Authorization": f"Bearer {self.channel_access_token}"},
                        json={"chatId": user_id, "loadingSeconds": loading_seconds},
                    )
            if response.status_code == 202:
                return True
            logger.warning("line_loading_unavailable status=%s", response.status_code)
        except Exception as error:
            # Do not log request headers, token, user ID or provider response body.
            logger.warning("line_loading_unavailable error_type=%s", type(error).__name__)
        return False

    def reply_message(
        self,
        reply_token: str,
        text: str = None,
        flex_message: dict = None,
        quote_token: Optional[str] = None
    ) -> None:
        """
        Reply to a LINE message with optional quote (supports both Text and Flex messages).

        Args:
            reply_token: Reply token from LINE webhook event
            text: Text message to send (use this OR flex_message)
            flex_message: Flex message dict to send (use this OR text)
            quote_token: Optional quote token to reference the original message
        """
        try:
            with ApiClient(self.configuration) as api_client:
                line_bot_api = MessagingApi(api_client)

                # Create message based on type
                if flex_message:
                    print(f"Creating Flex Message...")
                    # Create Flex Message with optional quote token
                    # Convert dict to FlexContainer using from_dict
                    from linebot.v3.messaging.models import FlexContainer as FlexContainerModel

                    contents_dict = flex_message.get("contents")
                    print(f"Flex contents type: {type(contents_dict)}")
                    print(f"Flex contents: {contents_dict}")

                    flex_container = FlexContainerModel.from_dict(contents_dict)
                    print(f"FlexContainer created: {type(flex_container)}")

                    message = FlexMessage(
                        alt_text=flex_message.get("alt_text", "Fraud Detection Result"),
                        contents=flex_container,
                        quote_token=quote_token
                    )
                    print(f"FlexMessage created with quote_token={quote_token}")
                elif text:
                    # Create text message with optional quote token
                    if quote_token:
                        message = TextMessage(text=text, quote_token=quote_token)
                    else:
                        message = TextMessage(text=text)
                else:
                    raise ValueError("Either text or flex_message must be provided")

                print(f"Sending message via LINE API...")
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[message]
                    )
                )
                print(f"Message sent successfully!")
        except Exception as e:
            print(f"ERROR in reply_message: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"Stack trace:\n{traceback.format_exc()}")
            raise

    def create_url_verification_flex_message(self, result: dict) -> dict:
        """Use the three compact result designs; keep full evidence in History."""
        return _create_result_flex_message(result, is_url=True)


    def create_fraud_flex_message(
        self,
        classification: str,
        is_fraud: bool,
        message_hash: Optional[str] = None,
        url_check: Optional[dict] = None,
        similarity_data: Optional[dict] = None,
        history_id: Optional[str] = None,
        confidence_score: Optional[float] = None,
        is_safe: Optional[bool] = None,
        has_malicious_urls: bool = False,
    ) -> dict:
        """Use the same risk/unknown/clear designs as URL results, without scores."""
        return _create_result_flex_message({
            "category": classification, "is_fraud": is_fraud, "is_safe": is_safe,
            "url_check": url_check, "history_id": history_id,
            "has_malicious_urls": has_malicious_urls,
        }, is_url=False)

    def create_fraud_response(
        self,
        classification: str,
        is_fraud: bool,
        url_check: Optional[dict] = None,
        similarity_data: Optional[dict] = None
    ) -> str:
        """
        Create a user-friendly response message based on fraud classification.

        Args:
            classification: The fraud classification result
            is_fraud: Whether the message is fraudulent
            url_check: VirusTotal URL check results (optional)
            similarity_data: TF-IDF similarity analysis results (optional)

        Returns:
            Formatted response text for LINE user
        """
        # Check for malicious URLs
        url_warning = ""
        if url_check and url_check.get("is_dangerous"):
            malicious_urls = url_check.get("malicious_urls", [])
            url_warning = (
                f"\n\nพบลิงก์อันตราย ({len(malicious_urls)} ลิงก์):\n"
                "ลิงก์นี้ถูกระบุว่าเป็นอันตรายโดย antivirus หลายตัว\n"
                "• อย่าคลิกลิงก์นี้เด็ดขาด\n"
                "• อาจเป็น phishing หรือ malware\n"
            )

        # Add similarity information if available
        similarity_info = ""
        if similarity_data:
            frequency = similarity_data.get("frequency", {})
            danger_analysis = similarity_data.get("danger_analysis", {})

            times_seen = frequency.get("times_seen", 0)
            danger_percentage = danger_analysis.get("danger_percentage", 0)
            total_fraud_messages = danger_analysis.get("total_fraud_messages", 0)

            # Only show similarity info if we have data
            if times_seen > 1 or danger_percentage > 0:
                similarity_info = f"\n\nข้อมูลเพิ่มเติม:\n"

                if times_seen > 1:
                    similarity_info += f"• ข้อความนี้ถูกรายงานแล้ว {times_seen} ครั้ง\n"

                if total_fraud_messages > 0:
                    similarity_info += f"• เทียบกับฐานข้อมูล {total_fraud_messages} ข้อความ"

        if classification == "FRAUD_GAMBLING_AD":
            return (
                "ข้อความนี้มีลักษณะเป็นโฆษณาการพนันออนไลน์\n\n"
                "คำเตือน:\n"
                "• อาจเป็นการพนันผิดกฎหมาย\n"
                "• ระวังการหลอกลวงทางการเงิน\n"
                "• ไม่แนะนำให้คลิกลิงก์หรือโอนเงิน\n\n"
                "ควรรายงานข้อความนี้หรือลบทิ้ง"
                + similarity_info
                + url_warning
            )
        elif classification == "SCAM_MALICIOUS_INVITE":
            return (
                "ข้อความนี้มีลักษณะพยายามหลอกลวง\n\n"
                "คำเตือน:\n"
                "• อาจเป็น Phishing หรือ Social Engineering\n"
                "• ระวังการขอข้อมูลส่วนตัว\n"
                "• ไม่ควรคลิกลิงก์ที่น่าสงสัย\n"
                "• ไม่ควรให้ข้อมูลธนาคารหรือรหัสผ่าน\n\n"
                "ควรรายงานข้อความนี้หรือลบทิ้ง"
                + similarity_info
                + url_warning
            )
        else:  # SAFE_NORMAL
            # If URL is dangerous but message looks safe
            if url_check and url_check.get("is_dangerous"):
                return (
                    "ข้อความดูปกติ แต่พบลิงก์อันตราย!\n\n"
                    "คำเตือนสำคัญ:\n"
                    "• ลิงก์ในข้อความนี้ถูกระบุว่าเป็นอันตราย\n"
                    "• อย่าคลิกลิงก์นี้เด็ดขาด\n"
                    "• อาจเป็น phishing, malware, หรือไวรัส\n\n"
                    "ควรรายงานข้อความนี้หรือลบทิ้ง"
                )
            else:
                return (
                    "ข้อความนี้ดูปลอดภัย\n\n"
                    "ไม่พบสัญญาณของการหลอกลวงหรือการพนันผิดกฎหมาย\n\n"
                    "อย่างไรก็ตาม ควรใช้วิจารณญาณในการตัดสินใจเสมอ"
                )

    def verify_signature(self, body: str, signature: str) -> bool:
        """
        Verify LINE webhook signature.

        Args:
            body: Request body as string
            signature: X-Line-Signature header value

        Returns:
            True if signature is valid

        Raises:
            InvalidSignatureError: If signature is invalid
        """
        try:
            self.handler.handle(body, signature)
            return True
        except InvalidSignatureError:
            return False


def _create_result_flex_message(result: dict, *, is_url: bool) -> dict:
    # Choose presentation from the actual verdict, not AI confidence/is_fraud.
    # Invalid, incomplete and unknown results must never become green cards.
    presentations = {
        "NO_THREAT_FOUND": ("green", "ไม่พบสัญญาณอันตราย", "จากการตรวจสอบ",
                            "โปรดใช้ความระมัดระวัง", "ไม่พบสัญญาณอันตรายจากการตรวจสอบ"),
        "SUSPICIOUS": ("red", "มีความเสี่ยง", "พบสัญญาณความเสี่ยง",
                       "ควรตรวจสอบเพิ่มเติม", "พบสัญญาณความเสี่ยง"),
        "MALICIOUS": ("red", "อันตราย!", "พบหลักฐานอันตราย",
                      "หลีกเลี่ยงการเปิดลิงก์", "พบหลักฐานอันตราย"),
        "INCOMPLETE": ("yellow", "ยังสรุปไม่ได้", "ตรวจสอบได้ไม่ครบ",
                       "ข้อมูลยังไม่เพียงพอ", "ยังสรุปไม่ได้ — ตรวจสอบได้ไม่ครบ"),
        "INVALID": ("yellow", "ยังสรุปไม่ได้", "ลิงก์ไม่ถูกต้อง",
                    "ตรวจสอบลิงก์อีกครั้ง", "ลิงก์ไม่ถูกต้องหรือปลายทางไม่อนุญาต"),
    }
    verdict = resolve_result_verdict(result, is_url=is_url)
    tone, title, badge, summary, label = presentations.get(verdict, presentations["INCOMPLETE"])
    start_color, end_color = {
        "green": ("#84FA50", "#4AB918"),
        "yellow": ("#FFD060", "#FF9500"),
        "red": ("#FF9500", "#FF3B30"),
    }[tone]
    if tone == "yellow":
        icon = {
            "type": "image",
            "url": "https://img.icons8.com/ios-filled/100/ffffff/question-mark.png",
            "size": "xs", "aspectRatio": "1:1", "margin": "md",
        }
    else:
        # Preserve the existing green/red circle icons and gradient colours.
        icon_url = ("https://img.icons8.com/ios-filled/100/4AB918/checkmark--v1.png"
                    if tone == "green" else
                    "https://img.icons8.com/ios-filled/100/FF3B30/high-priority.png")
        icon = {
            "type": "box", "layout": "vertical", "contents": [{
                "type": "box", "layout": "vertical", "contents": [{
                    "type": "image", "url": icon_url, "size": "xxs", "aspectRatio": "1:1",
                }], "width": "60px", "height": "60px", "backgroundColor": "#ffffff",
                "cornerRadius": "30px", "justifyContent": "center", "alignItems": "center",
            }], "alignItems": "center", "margin": "md",
        }
    return {
        "alt_text": f"ผลการตรวจสอบ{'ลิงก์' if is_url else 'ข้อความ'}: {label}",
        "contents": {
            "type": "bubble", "size": "mega",
            "body": {
                "type": "box", "layout": "vertical", "paddingAll": "lg",
                "contents": [
                    {"type": "text", "text": "GunGong", "size": "xs",
                     "weight": "bold", "color": "#ffffff", "align": "start"},
                    icon,
                    {"type": "text", "text": "ลิงก์ดังกล่าว" if is_url else "ข้อความดังกล่าว", "size": "sm",
                     "color": "#ffffff", "align": "center", "margin": "sm"},
                    {"type": "text", "text": title, "size": "xl",
                     "weight": "bold", "color": "#ffffff", "align": "center", "wrap": True},
                    {"type": "box", "layout": "vertical", "contents": [
                        {"type": "text", "text": badge, "size": "md",
                         "weight": "bold", "color": "#ffffff", "align": "center", "wrap": True},
                    ], "backgroundColor": "#ffffff44", "cornerRadius": "15px",
                     "paddingAll": "sm", "width": "60%", "margin": "sm"},
                    # Full explanations remain in the result saved to History.
                    {"type": "box", "layout": "vertical",
                     "contents": [{"type": "text", "text": summary,
                                   "size": "sm", "color": "#ffffff",
                                   "align": "center", "wrap": False}],
                     "backgroundColor": "#ffffff44", "cornerRadius": "md",
                     "paddingAll": "sm", "margin": "md"},
                    {"type": "text", "text": "see more >", "size": "xxs",
                     "color": "#ffffffcc", "align": "end", "margin": "sm"},
                ],
                "background": {"type": "linearGradient", "angle": "135deg",
                               "startColor": start_color, "endColor": end_color},
                "alignItems": "center",
                "action": {"type": "uri", "label": "เปิด Mini App",
                           "uri": _miniapp_history_uri(result.get("history_id"))},
            },
            "styles": {"body": {"backgroundColor": end_color}},
        },
    }


# Singleton instance
_line_service_instance = None


def get_line_service() -> LineService:
    """Get or create singleton LINE service instance."""
    global _line_service_instance
    if _line_service_instance is None:
        _line_service_instance = LineService()
    return _line_service_instance
