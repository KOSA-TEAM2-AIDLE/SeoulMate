"""API 명세서 6장"""
import json

from fastapi import APIRouter, HTTPException, Query

from core.config import DATA_DIR
from schemas.accommodations import Accommodation, AccommodationReview

router = APIRouter()


def _load(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _load_lang(base: str, lang: str) -> list[dict]:
    # en 데이터가 아직 없으면 ko로 폴백 (1단계 mock 한정)
    if lang == "en" and (DATA_DIR / f"{base}_en.json").exists():
        return _load(f"{base}_en.json")
    return _load(f"{base}.json")


def _find_accommodation(id: str, lang: str) -> dict:
    for acco in _load_lang("accommodation", lang):
        if acco["id"] == id:
            return acco
    raise HTTPException(status_code=404, detail="숙소를 찾을 수 없습니다")


@router.get("/accommodations", response_model=list[Accommodation])
def list_accommodations(lang: str = Query("ko")):
    return _load_lang("accommodation", lang)


@router.get("/accommodations/{id}", response_model=Accommodation)
def get_accommodation(id: str, lang: str = Query("ko")):
    return _find_accommodation(id, lang)


@router.get("/accommodations/{id}/reviews", response_model=list[AccommodationReview])
def list_accommodation_reviews(id: str, lang: str = Query("ko")):
    _find_accommodation(id, lang)
    return [r for r in _load_lang("accommodation_review", lang) if r["accommodation_id"] == id]
