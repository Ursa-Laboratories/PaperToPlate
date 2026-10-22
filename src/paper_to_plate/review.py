import hashlib
import json


def fingerprint(review: dict) -> str:
    return hashlib.sha256(json.dumps(review, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def human_clearance(run: dict) -> bool:
    decision = run.get("adjudication") or {}
    review = run.get("review") or {}
    if not decision.get("approved") or decision.get("protocol_hash") != run.get("protocol_hash") or decision.get("review_fingerprint") != fingerprint(review):
        return False
    if not decision.get("reviewer", "").strip() or len(decision.get("notes", "").strip()) < 20:
        return False
    for index, finding in enumerate(review.get("findings", [])):
        if finding["severity"] == "critical" and len(decision.get("finding_responses", {}).get(str(index), "").strip()) < 15:
            return False
    for index, question in enumerate(run.get("plan", {}).get("unresolved", [])):
        if len(decision.get("question_responses", {}).get(str(index), "").strip()) < 15:
            return False
    return True
