"""채팅창 표시용 최소 후보 응답."""

from domains.common.models import SearchCandidate


def build_chat_place(candidate: SearchCandidate, reason: str) -> dict:
    payload = {
        "domain": candidate.domain,
        "place_id": candidate.place_id,
        "name": candidate.name,
        "category": candidate.category,
        "selection_reason": reason,
    }
    if candidate.domain == "restaurant":
        payload["restaurant_id"] = candidate.place_id
    return payload


__all__ = ["build_chat_place"]

