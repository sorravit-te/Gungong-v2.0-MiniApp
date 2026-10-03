// LIFF Configuration
// A separate Developing build can use its own internal channel without changing
// the existing Published app. Never derive this ID from query parameters.
export const LIFF_ID = import.meta.env?.VITE_LIFF_ID || "2008548759-KkM4Noxa";
if (!/^[0-9]+-[A-Za-z0-9]+$/u.test(LIFF_ID)) throw new Error('INVALID_LIFF_ID');

function getPublicAssetUrl(path) {
    if (typeof window === 'undefined' || !window.location?.origin) {
        throw new Error("PUBLIC_ORIGIN_NOT_AVAILABLE");
    }

    const assetUrl = new URL(path, window.location.origin);
    const isLocalDevelopment = ["localhost", "127.0.0.1"].includes(assetUrl.hostname);

    if (assetUrl.protocol !== "https:" && !isLocalDevelopment) {
        throw new Error("PUBLIC_ORIGIN_MUST_USE_HTTPS");
    }

    return assetUrl.href;
}

// Initialize LIFF
export async function initLiff() {
    try {
        if (typeof window !== 'undefined' && window.liff) {
            await window.liff.init({ liffId: LIFF_ID });
            return true;
        }
    } catch (error) {
        console.error("LIFF init error:", error);
    }
    return false;
}

// Get User Profile
export async function getUserProfile() {
    try {
        if (window.liff && window.liff.isLoggedIn()) {
            const profile = await window.liff.getProfile();
            localStorage.setItem('userProfile', JSON.stringify(profile));
            return profile;
        }
    } catch (error) {
        console.error("getUserProfile error:", error);
    }

    // Return cached profile if available
    const cached = localStorage.getItem('userProfile');
    return cached ? JSON.parse(cached) : null;
}

// Get User ID (for API calls)
export async function getUserId() {
    if (typeof window !== 'undefined' && window.liff) {
        if (window.liff.isInClient() || window.liff.isLoggedIn()) {
            try {
                const profile = await window.liff.getProfile();
                return profile.userId;
            } catch (e) {
                console.warn("Error getting profile:", e);
            }
        }
    }
    // Anonymous browsers must not share a mock personal History identity.
    return null;
}

// Scan QR Code
export async function scanCode() {
    if (!window.liff) {
        throw new Error("LIFF not available");
    }

    // Check if LIFF is in client
    if (!window.liff.isInClient() && !window.liff.isLoggedIn()) {
        throw new Error("NOT_IN_LINE");
    }

    if (window.liff.scanCodeV2) {
        const result = await window.liff.scanCodeV2();
        return result.value;
    }

    throw new Error("SCAN_NOT_SUPPORTED");
}

// Share Mini App via Target Picker
export async function shareMiniApp() {
    if (!window.liff?.isInClient()) {
        throw new Error("NOT_IN_LINE");
    }

    const mascotUrl = getPublicAssetUrl("/img/mascot1.png");
    const message = [
        {
            type: "flex",
            altText: "ลองใช้ GunGong สิ! ช่วยเช็คโจรและมิจฉาชีพได้แม่นยำ",
            contents: {
                type: "bubble",
                hero: {
                    type: "image",
                    url: mascotUrl,
                    size: "full",
                    aspectRatio: "20:13",
                    aspectMode: "cover"
                },
                body: {
                    type: "box",
                    layout: "vertical",
                    contents: [
                        {
                            type: "text",
                            text: "GunGong (กันโกง)",
                            weight: "bold",
                            size: "xl",
                            color: "#3ACE00"
                        },
                        {
                            type: "text",
                            text: "แอปช่วยตรวจสอบลิงก์, SMS และบัญชีธนาคาร ป้องกันภัยออนไลน์ได้ทันที!",
                            wrap: true,
                            size: "sm",
                            color: "#666666",
                            margin: "md"
                        }
                    ]
                },
                footer: {
                    type: "box",
                    layout: "vertical",
                    contents: [
                        {
                            type: "button",
                            action: {
                                type: "uri",
                                label: "ลองใช้งานเลย",
                                uri: `https://liff.line.me/${LIFF_ID}`
                            },
                            style: "primary",
                            color: "#3ACE00"
                        }
                    ]
                }
            }
        }
    ];

    if (window.liff.isApiAvailable("shareTargetPicker")) {
        const res = await window.liff.shareTargetPicker(message);
        return !!res;
    }

    throw new Error("SHARE_NOT_SUPPORTED");
}

// Share Verification Card
export async function shareVerificationCard(profile, level = 'silver') {
    if (!window.liff?.isInClient()) {
        throw new Error("NOT_IN_LINE");
    }

    const baseUrl = getPublicAssetUrl("/img");

    const cardConfig = {
        silver: {
            title: 'SILVER',
            color: '#696969',
            bgUrl: `${baseUrl}/silver_card.png`
        },
        gold: {
            title: 'GOLD',
            color: '#8a6d3b',
            bgUrl: `${baseUrl}/gold_card.png`
        },
        diamond: {
            title: 'DIAMOND',
            color: '#5286e0',
            bgUrl: `${baseUrl}/diamond_card.png`
        }
    };

    const config = cardConfig[level] || cardConfig.silver;
    const userProfile = profile || {
        displayName: 'Guest',
        userId: '-',
        pictureUrl: 'https://vos.line-scdn.net/imgs/apis/ic_mini.png'
    };

    const flexMessage = {
        type: "flex",
        altText: `บัตรประจำตัว GunGong: ${userProfile.displayName}`,
        contents: {
            type: "bubble",
            size: "giga",
            body: {
                type: "box",
                layout: "vertical",
                contents: [
                    {
                        type: "image",
                        url: config.bgUrl,
                        size: "full",
                        aspectMode: "cover",
                        aspectRatio: "1.91:1",
                        gravity: "center"
                    },
                    {
                        type: "box",
                        layout: "horizontal",
                        position: "absolute",
                        offsetAll: "0px",
                        contents: [
                            {
                                type: "box",
                                layout: "vertical",
                                flex: 6,
                                paddingAll: "20px",
                                justifyContent: "space-between",
                                contents: [
                                    {
                                        type: "box",
                                        layout: "horizontal",
                                        contents: [
                                            {
                                                type: "box",
                                                layout: "vertical",
                                                width: "40px",
                                                height: "40px",
                                                backgroundColor: "#ffffff",
                                                cornerRadius: "20px",
                                                justifyContent: "center",
                                                alignItems: "center",
                                                contents: [
                                                    { type: "icon", url: "https://scdn.line-apps.com/n/channel_devcenter/img/fx/shield.png", size: "20px" }
                                                ]
                                            },
                                            {
                                                type: "box",
                                                layout: "vertical",
                                                paddingStart: "10px",
                                                contents: [
                                                    {
                                                        type: "text",
                                                        text: "ระดับการยืนยัน",
                                                        size: "xxs",
                                                        color: config.color,
                                                        weight: "bold"
                                                    },
                                                    {
                                                        type: "text",
                                                        text: config.title,
                                                        size: "xl",
                                                        weight: "900",
                                                        color: config.color
                                                    }
                                                ]
                                            }
                                        ],
                                        alignItems: "center"
                                    },
                                    {
                                        type: "box",
                                        layout: "vertical",
                                        contents: [
                                            {
                                                type: "text",
                                                text: userProfile.displayName,
                                                weight: "bold",
                                                size: "lg",
                                                color: config.color,
                                                wrap: true
                                            },
                                            {
                                                type: "text",
                                                text: `User ID : ${(userProfile.userId || '-').substring(0, 8)}...`,
                                                size: "xxs",
                                                color: config.color
                                            }
                                        ]
                                    }
                                ]
                            },
                            {
                                type: "box",
                                layout: "vertical",
                                flex: 3,
                                alignItems: "center",
                                justifyContent: "center",
                                contents: [
                                    {
                                        type: "image",
                                        url: userProfile.pictureUrl || 'https://vos.line-scdn.net/imgs/apis/ic_mini.png',
                                        size: "70px",
                                        aspectMode: "cover",
                                        backgroundColor: "#ffffff",
                                        cornerRadius: "100px"
                                    }
                                ]
                            }
                        ]
                    }
                ],
                paddingAll: "0px",
                action: {
                    type: "uri",
                    label: "Open App",
                    uri: `https://liff.line.me/${LIFF_ID}`
                }
            }
        }
    };

    if (window.liff.isApiAvailable("shareTargetPicker")) {
        const result = await window.liff.shareTargetPicker([flexMessage]);
        return !!result;
    }

    throw new Error("SHARE_NOT_SUPPORTED");
}

// Check if in LINE client
export function isInLineClient() {
    return window.liff?.isInClient() ?? false;
}

// Check if logged in
export function isLoggedIn() {
    return window.liff?.isLoggedIn() ?? false;
}
