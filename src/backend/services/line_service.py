"""LINE Bot service for sending messages and handling webhooks."""

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
                    print(f"📨 Creating Flex Message...")
                    # Create Flex Message with optional quote token
                    # Convert dict to FlexContainer using from_dict
                    from linebot.v3.messaging.models import FlexContainer as FlexContainerModel

                    contents_dict = flex_message.get("contents")
                    print(f"📋 Flex contents type: {type(contents_dict)}")
                    print(f"📋 Flex contents: {contents_dict}")

                    flex_container = FlexContainerModel.from_dict(contents_dict)
                    print(f"✅ FlexContainer created: {type(flex_container)}")

                    message = FlexMessage(
                        alt_text=flex_message.get("alt_text", "Fraud Detection Result"),
                        contents=flex_container,
                        quote_token=quote_token
                    )
                    print(f"✅ FlexMessage created with quote_token={quote_token}")
                elif text:
                    # Create text message with optional quote token
                    if quote_token:
                        message = TextMessage(text=text, quote_token=quote_token)
                    else:
                        message = TextMessage(text=text)
                else:
                    raise ValueError("Either text or flex_message must be provided")

                print(f"📤 Sending message via LINE API...")
                line_bot_api.reply_message(
                    ReplyMessageRequest(
                        reply_token=reply_token,
                        messages=[message]
                    )
                )
                print(f"✅ Message sent successfully!")
        except Exception as e:
            print(f"❌ ERROR in reply_message: {type(e).__name__}: {str(e)}")
            import traceback
            print(f"Stack trace:\n{traceback.format_exc()}")
            raise

    def create_fraud_flex_message(
        self,
        classification: str,
        is_fraud: bool,
        message_hash: Optional[str] = None, # Added for feedback postback
        url_check: Optional[dict] = None,
        similarity_data: Optional[dict] = None,
        history_id: Optional[str] = None,
        confidence_score: Optional[float] = None
    ) -> dict:
        """
        Create a Flex Message for fraud detection results (3 levels: High Risk, Medium Risk, Safe).
        Args:
            classification: The fraud classification result
            is_fraud: Whether the message is fraudulent
            message_hash: The SHA-256 hash of the original message for feedback tracking
            url_check: VirusTotal URL check results (optional)
            similarity_data: TF-IDF similarity analysis results (optional)
        Returns:
            Flex message dict with contents and alt_text
        """
        # Base URI for Mini App
        base_uri = "https://miniapp.line.me/2008548759-KkM4Noxa"
        action_uri = f"{base_uri}?historyId={history_id}" if history_id else base_uri

        # --- 1. Determine Risk Level ---
        danger_percentage = 0
        if similarity_data:
            danger_analysis = similarity_data.get("danger_analysis", {})
            danger_percentage = danger_analysis.get("danger_percentage", 0)

        if is_fraud and danger_percentage >= 70:
            risk_level = "high"
        elif is_fraud or danger_percentage >= 30:
            risk_level = "medium"
        else:
            risk_level = "safe"

        if url_check and url_check.get("is_dangerous"):
            risk_level = "high"
            danger_percentage = max(danger_percentage, 95.0)
            print("📈 OVERRIDE: Malicious URL detected. Forcing risk level to HIGH.")

        # --- 2. Define Feedback Footer ---
        # The postback data is a query string that will be handled by the webhook
        original_assessment = "fraud" if is_fraud else "safe"
        
        # Feedback footer removed as per user request (moved to popup)
        footer_block = None


        if is_fraud:
            # FRAUD - Red/Orange gradient
            bubble = {
                "type": "bubble",
                "size": "mega",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "GunGong",
                            "weight": "bold",
                            "color": "#ffffff",
                            "size": "xs",
                            "align": "start"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "box",
                                    "layout": "vertical",
                                    "contents": [
                                        {
                                            "type": "image",
                                            "url": "https://img.icons8.com/ios-filled/100/FF3B30/high-priority.png",
                                            "size": "xxs",
                                            "aspectRatio": "1:1"
                                        }
                                    ],
                                    "width": "60px",
                                    "height": "60px",
                                    "backgroundColor": "#ffffff",
                                    "cornerRadius": "30px",
                                    "justifyContent": "center",
                                    "alignItems": "center",
                                    "margin": "none"
                                }
                            ],
                            "alignItems": "center",
                            "margin": "md"
                        },
                        {
                            "type": "text",
                            "text": "ลิ้งดังกล่าว",
                            "color": "#ffffff",
                            "align": "center",
                            "size": "sm",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": "อันตราย!",
                            "color": "#ffffff",
                            "align": "center",
                            "size": "xl",
                            "weight": "bold",
                            "margin": "none"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"ความเสี่ยง: {int(danger_percentage)}%",
                                    "color": "#ffffff",
                                    "align": "center",
                                    "weight": "bold",
                                    "size": "md"
                                 }
                            ],
                            "backgroundColor": "#ffffff44",
                            "cornerRadius": "15px",
                            "paddingAll": "sm",
                            "width": "60%",
                            "margin": "sm"
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [],
                            "justifyContent": "space-evenly",
                            "margin": "md"
                        },
                        {
                            "type": "text",
                            "text": "see more >",
                            "color": "#ffffffcc",
                            "size": "xxs",
                            "align": "end",
                            "margin": "sm"
                        }
                    ],
                    "background": {
                        "type": "linearGradient",
                        "angle": "135deg",
                        "startColor": "#FF9500",
                        "endColor": "#FF3B30"
                    },
                    "paddingAll": "lg",
                    "action": {
                        "type": "uri",
                        "label": "action",
                        "uri": action_uri
                    },
                    "alignItems": "center"
                },
                # "footer": footer_block, # Removed
                "styles": {
                    "body": {
                        "backgroundColor": "#FF3B30"
                    }
                }
            }
            alt_text = "🚨 อันตราย! พบข้อความฉ้อโกง"

        else:
            # SAFE - Green gradient
            bubble = {
                "type": "bubble",
                "size": "mega",
                "body": {
                    "type": "box",
                    "layout": "vertical",
                    "contents": [
                        {
                            "type": "text",
                            "text": "GunGong",
                            "weight": "bold",
                            "color": "#ffffff",
                            "size": "xs",
                            "align": "start"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "box",
                                    "layout": "vertical",
                                    "contents": [
                                        {
                                            "type": "image",
                                            "url": "https://img.icons8.com/ios-filled/100/4AB918/checkmark--v1.png",
                                            "size": "xxs",
                                            "aspectRatio": "1:1"
                                        }
                                    ],
                                    "width": "60px",
                                    "height": "60px",
                                    "backgroundColor": "#ffffff",
                                    "cornerRadius": "30px",
                                    "justifyContent": "center",
                                    "alignItems": "center",
                                    "margin": "none"
                                }
                            ],
                            "alignItems": "center",
                            "margin": "md"
                        },
                        {
                            "type": "text",
                            "text": "ลิ้งดังกล่าว",
                            "color": "#ffffff",
                            "align": "center",
                            "size": "sm",
                            "margin": "sm"
                        },
                        {
                            "type": "text",
                            "text": "ปลอดภัย",
                            "color": "#ffffff",
                            "align": "center",
                            "size": "xl",
                            "weight": "bold",
                            "margin": "none"
                        },
                        {
                            "type": "box",
                            "layout": "vertical",
                            "contents": [
                                {
                                    "type": "text",
                                    "text": f"ความเสี่ยง: {int(danger_percentage)}%",
                                    "color": "#ffffff",
                                    "align": "center",
                                    "weight": "bold",
                                    "size": "md"
                                 }
                            ],
                            "backgroundColor": "#ffffff44",
                            "cornerRadius": "15px",
                            "paddingAll": "sm",
                            "width": "60%",
                            "margin": "sm"
                        },
                        {
                            "type": "box",
                            "layout": "horizontal",
                            "contents": [],
                            "justifyContent": "space-evenly",
                            "margin": "md"
                        },
                        {
                            "type": "text",
                            "text": "see more >",
                            "color": "#ffffffcc",
                            "size": "xxs",
                            "align": "end",
                            "margin": "sm"
                        }
                    ],
                    "background": {
                        "type": "linearGradient",
                        "angle": "135deg",
                        "startColor": "#84FA50",
                        "endColor": "#4AB918"
                    },
                    "paddingAll": "lg",
                    "action": {
                        "type": "uri",
                        "label": "action",
                        "uri": action_uri
                    },
                    "alignItems": "center"
                },
                # "footer": footer_block, # Removed
                "styles": {
                    "body": {
                        "backgroundColor": "#4AB918"
                    }
                }
            }
            alt_text = "✅ ปลอดภัย ข้อความนี้ไม่มีอันตราย"

        return {
            "alt_text": alt_text,
            "contents": bubble
        }

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
                f"\n\n🔗 พบลิงก์อันตราย ({len(malicious_urls)} ลิงก์):\n"
                "⛔ ลิงก์นี้ถูกระบุว่าเป็นอันตรายโดย antivirus หลายตัว\n"
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
                similarity_info = f"\n\n📊 ข้อมูลเพิ่มเติม:\n"

                if times_seen > 1:
                    similarity_info += f"• ข้อความนี้ถูกรายงานแล้ว {times_seen} ครั้ง\n"

                if danger_percentage > 0 and total_fraud_messages > 0:
                    similarity_info += f"• ความคล้ายกับข้อความฉ้อโกง: {danger_percentage:.1f}%\n"
                    similarity_info += f"• เทียบกับฐานข้อมูล {total_fraud_messages} ข้อความ"

        if classification == "FRAUD_GAMBLING_AD":
            return (
                "⚠️ ข้อความนี้มีลักษณะเป็นโฆษณาการพนันออนไลน์\n\n"
                "🚨 คำเตือน:\n"
                "• อาจเป็นการพนันผิดกฎหมาย\n"
                "• ระวังการหลอกลวงทางการเงิน\n"
                "• ไม่แนะนำให้คลิกลิงก์หรือโอนเงิน\n\n"
                "💡 ควรรายงานข้อความนี้หรือลบทิ้ง"
                + similarity_info
                + url_warning
            )
        elif classification == "SCAM_MALICIOUS_INVITE":
            return (
                "🚨 ข้อความนี้มีลักษณะพยายามหลอกลวง\n\n"
                "⚠️ คำเตือน:\n"
                "• อาจเป็น Phishing หรือ Social Engineering\n"
                "• ระวังการขอข้อมูลส่วนตัว\n"
                "• ไม่ควรคลิกลิงก์ที่น่าสงสัย\n"
                "• ไม่ควรให้ข้อมูลธนาคารหรือรหัสผ่าน\n\n"
                "💡 ควรรายงานข้อความนี้หรือลบทิ้ง"
                + similarity_info
                + url_warning
            )
        else:  # SAFE_NORMAL
            # If URL is dangerous but message looks safe
            if url_check and url_check.get("is_dangerous"):
                return (
                    "⚠️ ข้อความดูปกติ แต่พบลิงก์อันตราย!\n\n"
                    "🚨 คำเตือนสำคัญ:\n"
                    "• ลิงก์ในข้อความนี้ถูกระบุว่าเป็นอันตราย\n"
                    "• อย่าคลิกลิงก์นี้เด็ดขาด\n"
                    "• อาจเป็น phishing, malware, หรือไวรัส\n\n"
                    "💡 ควรรายงานข้อความนี้หรือลบทิ้ง"
                )
            else:
                return (
                    "✅ ข้อความนี้ดูปลอดภัย\n\n"
                    "ไม่พบสัญญาณของการหลอกลวงหรือการพนันผิดกฎหมาย\n\n"
                    "💡 อย่างไรก็ตาม ควรใช้วิจารณญาณในการตัดสินใจเสมอ"
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


# Singleton instance
_line_service_instance = None


def get_line_service() -> LineService:
    """Get or create singleton LINE service instance."""
    global _line_service_instance
    if _line_service_instance is None:
        _line_service_instance = LineService()
    return _line_service_instance
