"""API 명세서 5장"""
import json

from fastapi import APIRouter, HTTPException, Query

from core.config import DATA_DIR
from schemas.restaurants import Restaurant, RestaurantReview

router = APIRouter()


def _load(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _load_lang(base: str, lang: str) -> list[dict]:
    # en 데이터가 아직 없으면 ko로 폴백 (1단계 mock 한정)
    if lang == "en" and (DATA_DIR / f"{base}_en.json").exists():
        return _load(f"{base}_en.json")
    return _load(f"{base}.json")


def _find_restaurant(id: str, lang: str) -> dict:
    for restaurant in _load_lang("restaurant", lang):
        if restaurant["id"] == id:
            return restaurant
    raise HTTPException(status_code=404, detail="맛집을 찾을 수 없습니다")


@router.get("/restaurants", response_model=list[Restaurant])
def list_restaurants(lang: str = Query("ko")):
    return _load_lang("restaurant", lang)


@router.get("/restaurants/{id}", response_model=Restaurant)
def get_restaurant(id: str, lang: str = Query("ko")):
    return _find_restaurant(id, lang)


@router.get("/restaurants/{id}/reviews", response_model=list[RestaurantReview])
def list_restaurant_reviews(id: str, lang: str = Query("ko")):
    _find_restaurant(id, lang)
    return [r for r in _load_lang("restaurant_review", lang) if r["restaurant_id"] == id]
