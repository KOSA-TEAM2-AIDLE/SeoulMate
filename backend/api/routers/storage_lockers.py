"""API 명세서 8장

주의: 실시간 잔여 칸 API 없음. locker_count는 전체 보관함 수이며 실시간 잔여 칸이 아님.
리뷰 엔드포인트 없음 (cafes/restaurants/accommodations/events와 다름).
"""
import json

from fastapi import APIRouter, HTTPException, Query

from core.config import DATA_DIR
from schemas.storage_lockers import StorageLocker

router = APIRouter()


def _load(filename: str) -> list[dict]:
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)


def _load_lang(base: str, lang: str) -> list[dict]:
    # en 데이터가 아직 없으면 ko로 폴백 (1단계 mock 한정)
    if lang == "en" and (DATA_DIR / f"{base}_en.json").exists():
        return _load(f"{base}_en.json")
    return _load(f"{base}.json")


@router.get("/storage-lockers", response_model=list[StorageLocker])
def list_storage_lockers(lang: str = Query("ko")):
    return _load_lang("storage_locker", lang)


@router.get("/storage-lockers/{id}", response_model=StorageLocker)
def get_storage_locker(id: int, lang: str = Query("ko")):
    for locker in _load_lang("storage_locker", lang):
        if locker["id"] == id:
            return locker
    raise HTTPException(status_code=404, detail="물품보관소를 찾을 수 없습니다")
