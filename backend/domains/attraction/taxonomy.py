from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryDefinition:
    label: str
    aliases: tuple[str, ...]
    primary: str | None = None


PRIMARY_CATEGORIES: dict[str, CategoryDefinition] = {
    "culture": CategoryDefinition(
        "문화관광",
        ("문화관광", "문화시설", "문화 명소", "culture", "cultural attraction"),
    ),
    "shopping": CategoryDefinition("쇼핑", ("쇼핑 관광", "쇼핑", "shopping")),
    "history": CategoryDefinition("역사관광", ("역사관광", "역사 명소", "history", "historical attraction", "historic attraction")),
    "nature": CategoryDefinition("자연관광", ("자연관광", "자연 명소", "nature", "natural attraction", "natural scenery")),
    "experience": CategoryDefinition("체험관광", ("체험관광", "체험", "액티비티", "experience programs", "experience", "activity", "hands-on experience")),
    "event": CategoryDefinition("축제/공연/행사", ("축제 공연 행사", "축제/공연/행사", "festivals/events/performances")),
}


def _category(label: str, primary: str, *aliases: str) -> CategoryDefinition:
    return CategoryDefinition(label, (label, *aliases), primary)


SECONDARY_CATEGORIES: dict[str, CategoryDefinition] = {
    "exhibition": _category("전시시설", "culture", "전시", "전시회", "박물관", "미술관", "갤러리", "기념관", "cultural facilities", "museum", "art museum", "gallery", "exhibition", "memorial museum"),
    "cultural_district": _category("문화지구", "culture", "문화 거리", "문화마을", "예술 거리", "예술마을", "cultural districts", "cultural district", "art district", "art village"),
    "landmark": _category("랜드마크관광", "culture", "랜드마크", "전망대", "전망 명소", "타워", "landmarks", "landmark", "observatory", "observation deck", "tower"),
    "urban_park": _category("도시공원", "culture", "근린공원", "공원", "parks", "city park", "urban park", "park"),
    "other_culture": _category("기타문화관광지", "culture", "문화 명소", "other cultural destinations", "other cultural destination", "cultural destination"),
    "leisure_sports": _category("레저스포츠시설", "culture", "레저", "스포츠 시설", "체육 시설", "운동 시설", "leisure/sports centers", "leisure sports", "sports center", "sports facility", "recreation center"),
    "performance_hall": _category("공연시설", "culture", "공연장", "극장", "콘서트홀", "음악당", "performance halls", "performance hall", "theater", "theatre", "concert hall", "auditorium"),
    "education_center": _category("교육시설", "culture", "교육관", "학습관", "education centers", "education center", "educational facility", "learning center"),
    "convention_center": _category("행사시설", "culture", "컨벤션", "컨벤션센터", "회의장", "convention centers", "convention center", "event venue", "conference center"),
    "theme_park": _category("테마공원", "culture", "테마파크", "놀이공원", "theme parks", "theme park", "amusement park"),
    "specialty_shop": _category("전문매장/상가", "shopping", "전문매장", "상가", "전문점", "쇼핑 거리", "specialty shops & stores", "specialty shop", "specialty store", "shopping street", "shopping complex"),
    "market": _category("시장", "shopping", "전통시장", "재래시장", "traditional markets", "traditional market", "street market", "market"),
    "shopping_mall": _category("쇼핑몰", "shopping", "아울렛", "복합 쇼핑몰", "shopping malls & outlets", "shopping mall", "mall", "shopping outlet", "outlet"),
    "department_store": _category("백화점", "shopping", "department stores", "department store"),
    "duty_free": _category("면세점", "shopping", "면세 쇼핑", "duty free shops", "duty free", "duty-free shop"),
    "supermarket": _category("대형마트", "shopping", "마트", "창고형 마트", "supermarkets & warehouses", "supermarket", "hypermarket", "warehouse store"),
    "historical_site": _category("역사유적지", "history", "역사 유적", "유적지", "궁궐", "성곽", "고궁", "historical sites", "historical site", "historic site", "palace", "fortress", "heritage site"),
    "religious_site": _category("종교성지", "history", "종교 시설", "사찰", "성당", "교회", "religious sites", "religious site", "temple", "church", "cathedral", "shrine"),
    "natural_park": _category("자연공원", "nature", "국립공원", "생태공원", "natural sites(parks)", "natural park", "national park", "ecological park"),
    "mountain_scenery": _category("자연경관(산)", "nature", "등산", "산행", "둘레길", "숲", "natural sites(mountains)", "mountain", "hiking", "trail", "forest"),
    "river_scenery": _category("자연경관(하천)", "nature", "하천", "한강", "수변", "natural sites(rivers)", "river", "stream", "riverside", "waterfront", "han river"),
    "other_experience": _category("기타체험", "experience", "체험 프로그램", "이색 체험", "other experiences", "experience program", "unique experience"),
    "industrial_tourism": _category("산업관광", "experience", "산업시설", "공장 견학", "기업 견학", "industrial sites", "industrial tourism", "industrial site", "factory tour"),
    "craft_experience": _category("공예체험", "experience", "공방", "공예", "만들기 체험", "원데이 클래스", "craft workshops", "craft workshop", "craft experience", "one-day class"),
    "traditional_experience": _category("전통체험", "experience", "한복체험", "전통문화 체험", "traditional experience", "cultural experience", "hanbok experience"),
    "wellness": _category("웰니스관광", "experience", "웰니스", "힐링", "명상", "휴식", "wellness", "healing", "meditation", "relaxation"),
    "temple_stay": _category("산사체험", "experience", "템플스테이", "temple stays", "temple stay", "templestay"),
    "festival": _category("축제", "event", "페스티벌", "festivals", "festival"),
    "event": _category("행사", "event", "이벤트", "events", "event"),
    "performance": _category("공연", "event", "콘서트", "연극", "뮤지컬", "performances", "performance", "concert", "musical"),
}


_SHORT_EXACT_TERMS = {"궁", "산", "강", "천", "절", "park", "play", "shop"}


def _pattern(term: str) -> re.Pattern[str]:
    normalized = term.lower().strip()
    escaped = re.escape(normalized).replace(r"\ ", r"\s+")
    if re.search(r"[a-z0-9]", normalized) or normalized in _SHORT_EXACT_TERMS or len(normalized) <= 1:
        return re.compile(rf"(?<![가-힣a-z0-9]){escaped}(?![가-힣a-z0-9])", re.IGNORECASE)
    return re.compile(escaped, re.IGNORECASE)


def _matches(text: str, definition: CategoryDefinition) -> bool:
    return any(_pattern(alias).search(text) for alias in sorted(definition.aliases, key=len, reverse=True))


def _match_spans(text: str, definition: CategoryDefinition) -> list[tuple[int, int]]:
    return [match.span() for alias in definition.aliases for match in _pattern(alias).finditer(text)]


def categories_for_text(parts: Iterable[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    text = " ".join(part.lower().strip() for part in parts if part).strip()
    spans = {key: _match_spans(text, definition) for key, definition in SECONDARY_CATEGORIES.items()}
    secondary = tuple(
        key for key, matches in spans.items()
        if matches and any(
            not any(
                other_start <= start and end <= other_end and other_end - other_start > end - start
                for other_key, other_matches in spans.items() if other_key != key
                for other_start, other_end in other_matches
            )
            for start, end in matches
        )
    )
    explicit_primary = [key for key, definition in PRIMARY_CATEGORIES.items() if _matches(text, definition)]
    derived_primary = [SECONDARY_CATEGORIES[key].primary for key in secondary]
    primary = tuple(dict.fromkeys(key for key in [*explicit_primary, *derived_primary] if key))
    return primary, secondary


def normalize_metadata_category(category: str) -> tuple[str | None, str | None]:
    segments = [segment.strip().lower() for segment in re.split(r"\s*(?:>|/>)\s*", category or "") if segment.strip()]
    primary = next((key for key, definition in PRIMARY_CATEGORIES.items() if any(segment == alias.lower() for segment in segments for alias in (definition.label, *definition.aliases))), None)
    secondary = next((key for key, definition in SECONDARY_CATEGORIES.items() if any(segment == alias.lower() for segment in segments for alias in (definition.label, *definition.aliases))), None)
    if secondary and not primary:
        primary = SECONDARY_CATEGORIES[secondary].primary
    return primary, secondary


def category_metadata(category: str, kind: str) -> dict[str, str | None]:
    primary, secondary = normalize_metadata_category(category)
    if kind == "event":
        primary = primary or "event"
    return {"category_primary": primary, "category_secondary": secondary}
