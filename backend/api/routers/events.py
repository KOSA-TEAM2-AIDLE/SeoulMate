"""API 명세서 7장"""
import json
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from core.config import DATA_DIR
from schemas.events import Event, EventReview

router = APIRouter()


def _load(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _load_lang(base: str, lang: str) -> list[dict]:
    # en 데이터가 아직 없으면 ko로 폴백 (1단계 mock 한정)
    if lang == "en" and (DATA_DIR / f"{base}_en.json").exists():
        return _load(f"{base}_en.json")
    return _load(f"{base}.json")


def _find_event(id: str, lang: str) -> dict:
    for event in _load_lang("event", lang):
        if event["id"] == id:
            return event
    raise HTTPException(status_code=404, detail="행사를 찾을 수 없습니다")


@router.get("/events", response_model=list[Event])
def list_events(
    lang: str = Query("ko"),
    area_code: Optional[str] = Query(None),
    limit: int = Query(10),
):
    # TODO: area_code 필터는 mock 데이터에 서울 실시간 도시데이터 장소코드 매핑이 없어 아직 미구현.
    #       2단계에서 area_code <-> 행사 위치 매핑이 준비되면 필터링 추가.
    events = _load_lang("event", lang)
    return events[:limit]


@router.get("/events/{id}", response_model=Event)
def get_event(id: str, lang: str = Query("ko")):
    return _find_event(id, lang)


@router.get("/events/{id}/reviews", response_model=list[EventReview])
def list_event_reviews(id: str, lang: str = Query("ko")):
    _find_event(id, lang)
    return [r for r in _load_lang("event_review", lang) if r["event_id"] == id]
