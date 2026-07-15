"""API 명세서 4장"""
import json

from fastapi import APIRouter, HTTPException, Query

from core.config import DATA_DIR
from schemas.cafes import Cafe, CafeReview

router = APIRouter()


def _load(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _load_lang(base: str, lang: str) -> list[dict]:
    # en 데이터가 아직 없으면 ko로 폴백 (1단계 mock 한정)
    if lang == "en" and (DATA_DIR / f"{base}_en.json").exists():
        return _load(f"{base}_en.json")
    return _load(f"{base}.json")


@router.get("/cafes", response_model=list[Cafe])
def list_cafes(lang: str = Query("ko")):
    return _load_lang("cafe", lang)


def _find_cafe(id: str, lang: str) -> dict:
    for cafe in _load_lang("cafe", lang):
        if cafe["id"] == id:
            return cafe
    raise HTTPException(status_code=404, detail="카페를 찾을 수 없습니다")


@router.get("/cafes/{id}", response_model=Cafe)
def get_cafe(id: str, lang: str = Query("ko")):
    return _find_cafe(id, lang)


@router.get("/cafes/{id}/reviews", response_model=list[CafeReview])
def list_cafe_reviews(id: str, lang: str = Query("ko")):
    _find_cafe(id, lang)
    return [r for r in _load_lang("cafe_review", lang) if r["cafe_id"] == id]
