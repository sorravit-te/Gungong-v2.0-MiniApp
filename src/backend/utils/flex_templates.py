"""Flex Message Templates for LINE Bot."""

from linebot.v3.messaging.models import (
    FlexMessage, FlexBubble, FlexBox, FlexText, FlexSeparator, FlexIcon
)


def create_id_card_verification_flex(
    id_number: str,
    name_th: str,
    surname_th: str,
    date_of_birth: str,
    address: str,
    is_blacklisted: bool,
    is_valid_format: bool,
    risk_level: str,
    reports_count: int
) -> FlexMessage:
    """
    Create a beautiful Flex Message for ID card verification results.

    Args:
        id_number: Thai ID number
        name_th: First name in Thai
        surname_th: Surname in Thai
        date_of_birth: Date of birth
        address: Address
        is_blacklisted: Whether ID is blacklisted
        is_valid_format: Whether ID format is valid
        risk_level: Risk level (LOW, MEDIUM, HIGH, CRITICAL)
        reports_count: Number of reports

    Returns:
        FlexMessage object ready to send
    """

    # Determine status and colors
    if is_blacklisted:
        status_text = "พบในบัญชีดำ"
        status_color = "#FF4444"
        header_color = "#FF6B6B"
        safety_text = "ไม่ปลอดภัย"
        safety_percentage = "0%"
    elif not is_valid_format:
        status_text = "รูปแบบไม่ถูกต้อง"
        status_color = "#FF8C00"
        header_color = "#FFA500"
        safety_text = "ควรตรวจสอบ"
        safety_percentage = "50%"
    else:
        status_text = "ปลอดภัย"
        status_color = "#00C851"
        header_color = "#7FD957"
        safety_text = "ปลอดภัย"
        safety_percentage = "100%"

    # Display full address without truncation
    display_address = address

    # Build Flex Message
    bubble = FlexBubble(
        size="mega",
        header=FlexBox(
            layout="vertical",
            contents=[
                FlexText(
                    text="GunGong",
                    color="#FFFFFF",
                    size="md",
                    weight="bold",
                    align="center"
                )
            ],
            background_color=header_color,
            padding_all="sm"
        ),
        body=FlexBox(
            layout="vertical",
            contents=[
                # Status Icon and Text
                FlexBox(
                    layout="vertical",
                    contents=[
                        FlexText(
                            text="✓" if not is_blacklisted and is_valid_format else "!",
                            size="4xl",
                            weight="bold",
                            color="#FFFFFF",
                            align="center"
                        ),
                        FlexText(
                            text=safety_text,
                            size="xl",
                            weight="bold",
                            color="#FFFFFF",
                            align="center",
                            margin="md"
                        ),
                        FlexText(
                            text=status_text,
                            size="lg",
                            color="#FFFFFF",
                            align="center",
                            margin="xs"
                        ),
                        FlexText(
                            text=f"ความเสี่ยง: {safety_percentage}",
                            size="md",
                            color="#FFFFFF",
                            align="center",
                            margin="sm"
                        )
                    ],
                    background_color=status_color,
                    corner_radius="lg",
                    padding_all="lg",
                    margin="none"
                ),

                FlexSeparator(margin="lg"),

                # ID Card Details
                FlexText(
                    text="ข้อมูลบัตร:",
                    size="md",
                    weight="bold",
                    margin="lg",
                    color="#333333"
                ),

                # ID Number
                FlexBox(
                    layout="baseline",
                    contents=[
                        FlexText(
                            text="เลขบัตร:",
                            size="sm",
                            color="#666666",
                            flex=2
                        ),
                        FlexText(
                            text=id_number,
                            size="sm",
                            color="#333333",
                            flex=5,
                            wrap=True
                        )
                    ],
                    margin="md"
                ),

                # Name
                FlexBox(
                    layout="baseline",
                    contents=[
                        FlexText(
                            text="ชื่อ-นามสกุล:",
                            size="sm",
                            color="#666666",
                            flex=2
                        ),
                        FlexText(
                            text=f"{name_th} {surname_th}",
                            size="sm",
                            color="#333333",
                            flex=5,
                            wrap=True
                        )
                    ],
                    margin="sm"
                ),

                # Date of Birth
                FlexBox(
                    layout="baseline",
                    contents=[
                        FlexText(
                            text="วันเกิด:",
                            size="sm",
                            color="#666666",
                            flex=2
                        ),
                        FlexText(
                            text=date_of_birth,
                            size="sm",
                            color="#333333",
                            flex=5
                        )
                    ],
                    margin="sm"
                ),

                # Address
                FlexBox(
                    layout="baseline",
                    contents=[
                        FlexText(
                            text="ที่อยู่:",
                            size="sm",
                            color="#666666",
                            flex=2
                        ),
                        FlexText(
                            text=display_address,
                            size="sm",
                            color="#333333",
                            flex=5,
                            wrap=True
                        )
                    ],
                    margin="sm"
                ),

                FlexSeparator(margin="lg"),

                # Verification Details
                FlexText(
                    text="ผลการตรวจสอบ:",
                    size="md",
                    weight="bold",
                    margin="lg",
                    color="#333333"
                ),

                # Status
                FlexBox(
                    layout="baseline",
                    contents=[
                        FlexText(
                            text="สถานะ:",
                            size="sm",
                            color="#666666",
                            flex=2
                        ),
                        FlexText(
                            text=status_text,
                            size="sm",
                            color=status_color,
                            flex=5,
                            weight="bold"
                        )
                    ],
                    margin="md"
                ),

                # Risk Level
                FlexBox(
                    layout="baseline",
                    contents=[
                        FlexText(
                            text="ระดับความเสี่ยง:",
                            size="sm",
                            color="#666666",
                            flex=0
                        ),
                        FlexText(
                            text=risk_level,
                            size="sm",
                            color="#333333",
                            flex=0,
                            wrap=True,
                            margin="sm"
                        )
                    ],
                    margin="sm"
                ),

                # Report Count
                FlexBox(
                    layout="baseline",
                    contents=[
                        FlexText(
                            text="จำนวนรายงาน:",
                            size="sm",
                            color="#666666",
                            flex=0
                        ),
                        FlexText(
                            text=f"{reports_count} ครั้ง",
                            size="sm",
                            color="#333333",
                            flex=0,
                            wrap=True,
                            margin="sm"
                        )
                    ],
                    margin="sm"
                ),

                # Warning Box (if blacklisted)
                *([
                    FlexSeparator(margin="lg"),
                    FlexBox(
                        layout="vertical",
                        contents=[
                            FlexText(
                                text="⚠️ คำเตือน",
                                size="sm",
                                weight="bold",
                                color="#FF4444"
                            ),
                            FlexText(
                                text=f"เลขบัตรนี้มี {reports_count} รายงานการฉ้อโกง" if is_blacklisted else "เลขบัตรไม่ผ่านการตรวจสอบ checksum",
                                size="xs",
                                color="#666666",
                                margin="sm",
                                wrap=True
                            ),
                            FlexText(
                                text="ควรตรวจสอบกับหน่วยงานราชการเพิ่มเติม",
                                size="xs",
                                color="#666666",
                                margin="xs",
                                wrap=True
                            )
                        ],
                        background_color="#FFF3CD",
                        corner_radius="md",
                        padding_all="sm",
                        margin="md"
                    )
                ] if (is_blacklisted or not is_valid_format) else [])
            ],
            padding_all="lg"
        ),
        footer=FlexBox(
            layout="vertical",
            contents=[
                FlexText(
                    text="see more >",
                    size="xs",
                    color="#999999",
                    align="center"
                )
            ],
            padding_all="sm"
        )
    )

    return FlexMessage(
        alt_text=f"ผลการตรวจสอบบัตรประชาชน: {status_text}",
        contents=bubble
    )
