"""
Performance optimization configuration.

Controls timeouts, feature flags, and performance thresholds.
"""

from typing import Optional


class PerformanceConfig:
    """Performance optimization settings."""

    # ============ API Timeouts (seconds) ============
    # Aggressive timeouts to meet < 3s target for Hackathon

    # Gemini AI timeout
    GEMINI_TIMEOUT: float = 2.0

    # VirusTotal API timeout (per URL)
    VIRUSTOTAL_TIMEOUT: float = 1.5

    # URL expansion timeout (per URL)
    URL_EXPANSION_TIMEOUT: float = 0.5

    # Gambling detection timeout (Headless browser)
    GAMBLING_DETECTION_TIMEOUT: float = 2.5

    # Global timeout    # Maximum time for total processing (seconds)
    MAX_TOTAL_PROCESSING_TIME: float = 3.0

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
