"""Presentation only: never change the detector verdict or saved evidence."""


def resolve_result_verdict(result: dict, *, is_url: bool = False) -> str:
    url_check = result.get("url_check") or result.get("url_check_result") or {}
    # A clean/incomplete URL inside fraudulent text does not clear the text finding.
    if not is_url and not result.get("verification_verdict") and result.get("is_fraud") is True:
        return "SUSPICIOUS"
    verdict = result.get("verification_verdict") or url_check.get("verification_verdict")
    if verdict:
        return verdict if verdict in {"NO_THREAT_FOUND", "SUSPICIOUS", "MALICIOUS", "INCOMPLETE", "INVALID"} else "INCOMPLETE"
    if is_url:
        return "INCOMPLETE"
    if url_check.get("is_dangerous") is True or result.get("has_malicious_urls") is True or result.get("is_fraud") is True:
        return "SUSPICIOUS"
    if result.get("is_safe") is True or (result.get("is_fraud") is False and result.get("is_safe") is not False):
        return "NO_THREAT_FOUND"
    return "INCOMPLETE"
