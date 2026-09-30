# Production URL verification

The interactive `message_type="link"` path uses a bounded evidence pipeline. It normalizes an HTTP(S) URL, resolves redirects manually, validates DNS before every request, then evaluates the final destination with Gemini, VirusTotal, local URL heuristics, and bounded page evidence. Independent checks run concurrently after redirect resolution.

## Verdicts

- `MALICIOUS`: at least one source supplied malicious evidence.
- `SUSPICIOUS`: no malicious evidence exists, but at least one source supplied suspicious evidence.
- `NO_THREAT_FOUND`: every required source completed and none supplied malicious or suspicious evidence. This does not claim absolute safety.
- `INCOMPLETE`: no confirmed malicious evidence exists, but at least one required source timed out, was unavailable/rate-limited, returned pending/not-found, or errored. Incomplete is never safe.
- `INVALID`: the URL is malformed, unsupported, resolves to a prohibited destination, or violates redirect safety limits.

The legacy fields (`category`, `risk_level`, `is_fraud`, `is_safe`, and `url_check`) remain present. `is_safe` is `true` only for `NO_THREAT_FOUND`; it is `null` for `INCOMPLETE` and `INVALID`.

## Security and latency boundaries

Only HTTP and HTTPS are accepted. Every hostname is resolved before connection, and any loopback, private, carrier-grade, link-local, multicast, reserved, unspecified, or otherwise non-global address blocks the request. HTTP redirects and conservatively parsed HTML meta refreshes of at most five seconds are followed manually with one shared five-hop cap and two-second total budget; relative locations, loops, and public-to-private redirects are handled explicitly. JavaScript is never executed. Metadata records whether the bounded HTML preview contained no supported client redirect or could not be parsed safely. TLS verification remains enabled. Response content is streamed and capped at 64 KiB for interactive inspection. Playwright is not used by this path.

The page analyzer extracts bounded title, description, visible text, form/action, password/OTP, bank/authority impersonation, urgent-payment, and gambling signals. Script, style, template, and raw HTML are excluded. Gemini uses a dedicated URL/page prompt that labels the extracted webpage text as untrusted evidence and instructs the model to ignore instructions inside it; the ordinary user-message prompt is not reused. Only derived signals—not raw page text—are returned or cached. A page body that cannot be fetched or read makes content evidence incomplete rather than clean.

DNS validation and the HTTP connection are separate operations because the current HTTP client does not pin the validated address. This leaves a residual DNS-rebinding window between validation and connection. Production deployment therefore requires an outbound network policy that denies private, loopback, link-local, and metadata ranges even if DNS changes between validation and connection.

Configured budgets are 2 seconds for redirect resolution, 2.8 seconds for VirusTotal, 2 seconds for local/content analysis, 4.5 seconds for Gemini, 9 seconds overall, and 12 seconds in the frontend. Timed-out tasks are cancelled before the backend returns.

Legacy prescreening in `/check-fraud` text mode and the LINE webhook now performs local pattern analysis only. Its previous short-link/headless network enrichment did not enforce the SSRF boundary and is intentionally disabled; URL-mode checks use the bounded verifier, while text-mode URL reputation remains best-effort without headless browsing.

## VirusTotal and caching

VirusTotal is best-effort evidence. Its statuses are `clean`, `malicious`, `suspicious`, `not_found`, `pending`, `rate_limited`, `timeout`, `unavailable`, and `error`. Only a completed analysis with zero malicious and suspicious detections is `clean`. Unknown URLs are not uploaded by default (`VIRUSTOTAL_SUBMIT_UNKNOWN_URLS=false`); enabling submission has privacy and quota implications, and a new submission remains `pending`.

Completed VirusTotal evidence is normalized and cached locally. `not_found` remains incomplete but is cached in-process for 30 minutes to avoid repeatedly spending the free public quota on the same normalized URL. Pending, timeout, unavailable, error, and rate-limited results are not cached. In-flight duplicate lookups share one request. Local guards enforce the configured free-tier minute/day budgets and a cooldown after HTTP 429 without retrying inside the interactive request.

Only complete, non-invalid aggregate URL results enter the persistent one-day cache. Incomplete, pending, timeout, and partial results are not cached. Old cache entries without verdict/completeness metadata are ignored by the link pipeline.
