"""기존 식당 RAG dict와 공통 SearchCandidate 사이의 매퍼."""

from __future__ import annotations

from copy import deepcopy

from domains.common.models import SearchCandidate


def _evidence_texts(raw: dict) -> list[str]:
    evidence = raw.get("evidence") or {}
    texts: list[str] = []
    for review in evidence.get("reviews") or []:
        content = str(review.get("content") or "").strip()
        if content:
            texts.append(content)
    for menu in evidence.get("menus") or []:
        name = str(menu.get("menu_name") or menu.get("name") or "").strip()
        if name:
            texts.append(f"메뉴: {name}")
    return texts


def to_search_candidate(raw: dict, task_id: str) -> SearchCandidate:
    restaurant_id = str(raw.get("restaurant_id") or raw.get("id") or "")
    if not restaurant_id:
        raise ValueError("식당 후보에 restaurant_id가 없습니다.")
    base_score = float(raw.get("rag_score", raw.get("score", 0.0)) or 0.0)
    final_score = float(raw.get("score", base_score) or base_score)
    excluded = {
        "restaurant_id", "id", "name", "category", "lat", "lng",
        "score", "rag_score", "weather_score", "weather_reasons", "evidence",
    }
    attributes = {key: deepcopy(value) for key, value in raw.items() if key not in excluded}
    # 기존 날씨 재랭커와 완전히 같은 결과를 보장하는 단계적 마이그레이션용 원본.
    attributes["_legacy_raw"] = deepcopy(raw)
    return SearchCandidate(
        domain="restaurant",
        place_id=restaurant_id,
        task_id=task_id,
        name=str(raw.get("name") or "이름 없음"),
        category=str(raw.get("category") or raw.get("category_kakao") or "식당"),
        latitude=raw.get("lat"),
        longitude=raw.get("lng"),
        base_score=base_score,
        final_score=final_score,
        evidence=_evidence_texts(raw),
        attributes=attributes,
        signals={
            "rag_breakdown": deepcopy(raw.get("breakdown") or {}),
            "weather_score": raw.get("weather_score"),
            "weather_reasons": deepcopy(raw.get("weather_reasons") or []),
        },
    )


def to_legacy_candidate(candidate: SearchCandidate) -> dict:
    raw = deepcopy(candidate.attributes.get("_legacy_raw") or {})
    raw.update({
        "restaurant_id": candidate.place_id,
        "name": candidate.name,
        "category": candidate.category,
        "lat": candidate.latitude,
        "lng": candidate.longitude,
        "rag_score": candidate.base_score,
        "score": candidate.final_score,
    })
    return raw


__all__ = ["to_search_candidate", "to_legacy_candidate"]

