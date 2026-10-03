"""Local IAM-authorized review tool; defaults to a non-mutating preview.

Run from repository root: python -m scripts.reports.complete_review --help
Never expose this command as a public endpoint. This command does not send LINE
messages: submission acknowledgement is sent by the authenticated report flow.
"""
import argparse
import json

from src.backend.core.config import settings
from src.backend.services.database_service import get_database_service
from src.backend.services.report_service_messages import (
    REPORTS, RESULTS, ServiceMessageError, complete_review, read, validate_id,
)


def parser():
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("report_id", help="Full 64-character report receipt ID")
    result.add_argument("--project", required=True, help="Must match FIRESTORE_PROJECT_ID")
    result.add_argument("--reviewer", required=True, help="Operator audit label (not authentication)")
    result.add_argument("--result", required=True, choices=sorted(RESULTS))
    result.add_argument("--note", required=True, help="Public review explanation for the reporter")
    result.add_argument("--apply", action="store_true", help="Persist the completed review")
    result.add_argument("--confirm-reviewed", action="store_true", help="Confirm you actually reviewed the tip")
    return result


def run(args, cfg=settings, database=None):
    validate_id(args.report_id)
    if not cfg.firestore_project_id or args.project != cfg.firestore_project_id:
        raise ServiceMessageError("project_confirmation_mismatch")
    if (not args.reviewer.strip() or len(args.reviewer.strip()) > 80
            or not args.note.strip() or len(args.note.strip()) > 1000):
        raise ServiceMessageError("invalid_review")
    if args.apply and not args.confirm_reviewed:
        raise ServiceMessageError("review_confirmation_required")
    service = database if database is not None else get_database_service()
    if not service:
        raise ServiceMessageError("database_unavailable")
    db = service.db
    previous = read(db.collection(REPORTS).document(args.report_id))
    if not previous:
        raise ServiceMessageError("report_not_found")
    if not args.apply:
        return {"mode": "preview", "id": args.report_id, "current_status": previous.get("status"),
                "proposed_status": "reviewed", "result": args.result,
                "notification": "not_requested"}
    complete_review(db, args.report_id, args.reviewer, args.result, args.note)
    return {"mode": "applied", "id": args.report_id, "status": "reviewed",
            "notification": "not_requested"}


def main():
    args = parser().parse_args()
    try:
        result = run(args)
        print(json.dumps(result, ensure_ascii=True))
        return 0 if result.get("notification") in {"sent", "already_sent", "not_requested", "requested"} else 2
    except ServiceMessageError as error:
        print(json.dumps({"error": str(error)}))
    except Exception:
        # Exception messages may contain credentials or provider responses.
        print(json.dumps({"error": "operation_unconfirmed_check_status_before_retry"}))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
