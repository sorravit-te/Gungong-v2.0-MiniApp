"""Services package for backend application."""

# Import services conditionally to avoid dependency issues
__all__ = []

# URL Expander (sync version - requires requests)
try:
    from .url_expander_service import URLExpanderService, get_url_expander_service
    __all__.extend(["URLExpanderService", "get_url_expander_service"])
except ImportError:
    pass

# URL Expander (async version - requires httpx)
try:
    from .url_expander_service_async import (
        AsyncURLExpanderService,
        get_async_url_expander_service
    )
    __all__.extend(["AsyncURLExpanderService", "get_async_url_expander_service"])
except ImportError:
    pass

# VirusTotal service (sync version - requires requests)
try:
    from .virustotal_service import VirusTotalService, get_virustotal_service
    __all__.extend(["VirusTotalService", "get_virustotal_service"])
except ImportError:
    pass

# VirusTotal service (async version - requires httpx)
try:
    from .virustotal_service_async import (
        AsyncVirusTotalService,
        get_async_virustotal_service
    )
    __all__.extend(["AsyncVirusTotalService", "get_async_virustotal_service"])
except ImportError:
    pass

# Gemini service (requires langchain)
try:
    from .gemini_service import GeminiFraudDetector, get_fraud_detector
    __all__.extend(["GeminiFraudDetector", "get_fraud_detector"])
except ImportError:
    pass

# LINE service (optional due to Python 3.13 compatibility issues)
try:
    from .line_service import LineService
    __all__.append("LineService")
except (ImportError, SyntaxError):
    pass

# Gambling detector service (requires httpx, beautifulsoup4)
try:
    from .gambling_detector_service import GamblingDetectorService, get_gambling_detector
    __all__.extend(["GamblingDetectorService", "get_gambling_detector"])
except ImportError:
    pass

# Fraud message service (requires sklearn)
try:
    from .fraud_message_service import FraudMessageService, get_fraud_message_service
    __all__.extend(["FraudMessageService", "get_fraud_message_service"])
except ImportError:
    pass