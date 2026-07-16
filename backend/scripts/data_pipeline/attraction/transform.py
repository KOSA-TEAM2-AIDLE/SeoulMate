from datetime import date
import re
from typing import Iterable

from scripts.data_pipeline.attraction.models import FilterResult, ProcessedPlace, QuarantineRow


# 특정 카테고리의 경우 행사 시작 및 종료일이 있어서 이에 대하여 필터링 진행
EVENT_MARKERS = ("축제", "공연", "행사", "festival", "event", "performance")


def _text(value: object) -> str:
    return str(value or "").strip()


def _parse_date(value: object) -> date | None:
    text = _text(value)
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _number(value: object) -> float | None:
    try:
        return float(_text(value))
    except ValueError:
        return None


# 언어별 ID 값에 PREFIX 를 제거하기 위함
def make_place_key(cid: str) -> str:
    match = re.search(r"(?:KOP|ENP)?(.*)$", _text(cid), flags=re.IGNORECASE)
    return match.group(1) if match else _text(cid)


def _is_event(category: str) -> bool:
    lowered = category.casefold()
    return any(marker in lowered for marker in EVENT_MARKERS)


def classify_and_filter_rows(rows: Iterable[dict[str, object]], *, as_of: date) -> FilterResult:
    attractions: list[ProcessedPlace] = []
    events: list[ProcessedPlace] = []
    quarantine: list[QuarantineRow] = []
    seen: set[tuple[str, str]] = set()

    for raw in rows:
        cid = _text(raw.get("cid"))
        place_key = make_place_key(cid)
        lang = _text(raw.get("lang_code_id")).casefold()
        category = _text(raw.get("category_path"))
        name = _text(raw.get("name"))
        kind = "event" if _is_event(category) else "attraction"
        if not cid or not place_key or lang not in {"ko", "en"} or not name:
            quarantine.append(QuarantineRow(cid, place_key, name, "missing_identity"))
            continue
        if (place_key, lang) in seen:
            quarantine.append(QuarantineRow(cid, place_key, name, "duplicate_language_place"))
            continue
        seen.add((place_key, lang))
        start_date = _parse_date(raw.get("schedule_start_date"))
        end_date = _parse_date(raw.get("schedule_end_date"))
        if kind == "event":
            has_end_date = bool(_text(raw.get("schedule_end_date")))
            if has_end_date and end_date is None:
                quarantine.append(QuarantineRow(cid, place_key, name, "invalid_event_end_date"))
                continue
            if end_date is not None and end_date < as_of:
                quarantine.append(QuarantineRow(cid, place_key, name, "expired_event"))
                continue
        place = ProcessedPlace(
            place_key=place_key, source_cid=cid, lang=lang, kind=kind, category=category,
            name=name, summary=_text(raw.get("summary")), description=_text(raw.get("description_text")),
            road_address=_text(raw.get("road_address")) or _text(raw.get("jibun_address")),
            latitude=_number(raw.get("latitude")), longitude=_number(raw.get("longitude")),
            hours=_text(raw.get("use_time")), fee=_text(raw.get("usage_fee")),
            tags=_text(raw.get("tags")), homepage_url=_text(raw.get("homepage_url")),
            start_date=start_date, end_date=end_date,
        )
        (events if kind == "event" else attractions).append(place)
    return FilterResult(attractions, events, quarantine)
