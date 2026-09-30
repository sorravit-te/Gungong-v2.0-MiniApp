# Thai ID card verification contract

GunGong does not validate a person's identity against a Thai government registry. A successful result means only that the supplied number passes the Thai 13-digit Modulo-11 checksum and was not found in GunGong's fraud blacklist at the time of the lookup.

## Verification flows

- Manual number: normalize to 13 digits, validate the checksum, then query the Firestore fraud blacklist.
- Card image: validate and decode the JPEG/PNG image, use Gemini multimodal OCR to extract the 13-digit number, validate the checksum, then query the same Firestore fraud blacklist.

If Firestore cannot complete the blacklist lookup, verification fails closed with HTTP 503. The result must not be described as safe or not blacklisted. Invalid requests and unreadable images return JSON 4xx responses, while unexpected server failures return a generic JSON 500 response.

Blacklist risk levels use one report-count model for both flows:

- 20 or more reports: `CRITICAL`
- 10–19 reports: `HIGH`
- 5–9 reports: `MEDIUM`
- 1–4 reports: `LOW`

A non-blacklisted number with a valid checksum is `LOW`; a non-blacklisted number with an invalid checksum is `MEDIUM` and is not marked safe.

## Reference comparison

The implementation was compared with [`correleotion/idcard_checker`](https://github.com/correleotion/idcard_checker) at commit `7ff84623d96a919c9ce3527873702f86f71201ef`. GunGong retains the reference concepts of Modulo-11 validation, Gemini image OCR, Firestore blacklist lookup, and report-count risk calculation.

No reference file was copied wholesale. In particular, its stale manual-flow calls to `self.thai_id_validator` and `self.database_service.check_blacklist_id_card(...)` were not adopted; GunGong keeps its newer `validate_thai_id(...)` and `check_id_blacklist(...)` implementation.
