"""
Performance optimization configuration.

Controls timeouts, feature flags, and performance thresholds.
"""

from typing import Optional


class PerformanceConfig:
    """Performance optimization settings."""

    # ============ API Timeouts (seconds) ============
    # Interactive provider budgets.

    # Gemini AI timeout
    GEMINI_TIMEOUT: float = 4.5

    # VirusTotal API timeout (per URL)
    VIRUSTOTAL_TIMEOUT: float = 2.8

    # Total redirect-resolution timeout
    URL_EXPANSION_TIMEOUT: float = 3.0

    # Final page body has its own budget, still inside the global deadline.
    CONTENT_FETCH_TIMEOUT: float = 2.0

    # Browser startup, passive resources and DOM readiness share one budget.
    URL_RENDER_TIMEOUT: float = 4.0
    URL_RENDER_CLEANUP_ALLOWANCE: float = 1.8
    URL_RENDER_MAX_REQUESTS: int = 40
    URL_RENDER_RESOURCE_BYTES: int = 3 * 1024 * 1024
    URL_RENDER_TOTAL_BYTES: int = 8 * 1024 * 1024

    # Local/content analysis (the separate SPA fallback has its own budget)
    GAMBLING_DETECTION_TIMEOUT: float = 2.0

    # Maximum time for the URL evidence pipeline (seconds)
    MAX_TOTAL_PROCESSING_TIME: float = 9.0

    # Browser/client deadline is intentionally higher than this backend budget.
    FRONTEND_LINK_TIMEOUT: float = 12.0

    # Redirect and response limits for attacker-controlled URLs.
    MAX_REDIRECTS: int = 5
    MAX_CONTENT_PREVIEW_BYTES: int = 1024 * 1024

    # Minimum extracted visible text for a meaningful core page assessment.
    MIN_PAGE_VISIBLE_TEXT_CHARS: int = 80
    GEMINI_BENIGN_CONFIDENCE_THRESHOLD: float = 80.0

    # Bound synchronous Firestore operations around the interactive pipeline.
    DATABASE_OPERATION_TIMEOUT: float = 0.5

    # Dedicated URL core reputation RPC budget; other database operations stay unchanged.
    LOCAL_REPUTATION_LOOKUP_TIMEOUT: float = 1.0

    # Recent danger evidence is not a benign-result cache. Weak provider
    # detections expire sooner, and must never become a permanent blocklist.
    URL_RISK_READ_TIMEOUT: float = 1.0
    # Native RPC plus bounded scheduling/initialization allowance, never retries.
    URL_RISK_LOOKUP_TIMEOUT: float = 1.2
    URL_WEAK_RISK_TTL_SECONDS: int = 900
    URL_RISK_TTL_SECONDS: int = 3600
    URL_REPUTATION_TIMEOUT: float = 1.0

    # ============ Feature Flags ============
    # Enable/disable features for performance

    # Enable web scraping for gambling detection (SLOW - 1-2s)
    ENABLE_GAMBLING_SCRAPING: bool = True

    # Enable VirusTotal checks
    ENABLE_VIRUSTOTAL: bool = True

    # Enable URL expansion
    ENABLE_URL_EXPANSION: bool = True

    # Enable similarity analysis (can be slow for large DB)
    ENABLE_SIMILARITY_ANALYSIS: bool = True

    # Do similarity analysis in background (async)
    SIMILARITY_IN_BACKGROUND: bool = False

    # ============ Smart Routing Thresholds ============
    # Route based on pre-screen confidence for speed

    # If pre-screen confidence >= this, skip AI entirely (instant response)
    PRESCREEN_INSTANT_THRESHOLD: float = 0.8

    # If pre-screen confidence >= this, use AI only (skip URL checks)
    PRESCREEN_AI_ONLY_THRESHOLD: float = 0.5

    # Below this threshold, full check (AI + URLs + everything)
    PRESCREEN_FULL_CHECK_THRESHOLD: float = 0.5

    # ============ Caching Settings ============

    # URL reputation cache TTL (days)
    URL_CACHE_TTL_DAYS: int = 7

    # Provider 404s remain incomplete and are cached briefly only to protect
    # the very small public VirusTotal request budget.
    VIRUSTOTAL_NOT_FOUND_CACHE_TTL_SECONDS: float = 1800.0
    VIRUSTOTAL_COMPLETED_CACHE_TTL_SECONDS: float = 300.0

    # Free public VirusTotal API budget. The in-process guard is conservative;
    # provider-side limits remain authoritative across multiple app instances.
    VIRUSTOTAL_REQUESTS_PER_MINUTE: int = 4
    VIRUSTOTAL_REQUESTS_PER_DAY: int = 500
    VIRUSTOTAL_RATE_LIMIT_COOLDOWN: float = 60.0

    # Fraud check cache TTL (days)
    FRAUD_CHECK_CACHE_TTL_DAYS: int = 30

    # Domain blacklist refresh interval (hours)
    DOMAIN_BLACKLIST_REFRESH_HOURS: int = 24

    # ============ Deduplication Settings ============

    # Don't save new fraud message if similarity > this threshold
    FRAUD_MESSAGE_SIMILARITY_THRESHOLD: float = 0.7

    # Maximum fraud messages to keep in DB (for memory)
    MAX_FRAUD_MESSAGES: Optional[int] = 10000

    # ============ Model Selection ============

    # Gemini model - use faster model
    # Options: "gemini-1.5-flash" (faster), "gemini-2.5-flash-lite" (current)
    GEMINI_MODEL: str = "gemini-1.5-flash"

    # ============ Concurrency Settings ============

    # Max concurrent URL checks
    MAX_CONCURRENT_URL_CHECKS: int = 3

    # Max concurrent API calls
    MAX_CONCURRENT_API_CALLS: int = 5


# Singleton instance
_config = PerformanceConfig()


def get_performance_config() -> PerformanceConfig:
    """Get performance configuration instance."""
    return _config


# Convenience functions
def should_skip_ai(prescreen_confidence: float) -> bool:
    """Check if should skip AI based on pre-screen confidence."""
    return prescreen_confidence >= _config.PRESCREEN_INSTANT_THRESHOLD


def should_skip_url_checks(prescreen_confidence: float) -> bool:
    """Check if should skip URL checks based on pre-screen confidence."""
    return _config.PRESCREEN_AI_ONLY_THRESHOLD <= prescreen_confidence < _config.PRESCREEN_INSTANT_THRESHOLD


def should_do_full_check(prescreen_confidence: float) -> bool:
    """Check if should do full check."""
    return prescreen_confidence < _config.PRESCREEN_FULL_CHECK_THRESHOLD
