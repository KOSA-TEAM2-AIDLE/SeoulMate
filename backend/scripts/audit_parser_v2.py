"""식당 단일 추천용 Structured Query V2를 실제 GPT로 검증한다."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
from datetime import date, timedelta
from enum import Enum

from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


load_dotenv()


class ConstraintStrength(str, Enum):
    REQUIRED = "required"
    PREFERRED = "preferred"


class CuisineCode(str, Enum):
    KOREAN = "korean"
    JAPANESE = "japanese"
    CHINESE = "chinese"
    ITALIAN = "italian"
    THAI = "thai"
    VIETNAMESE = "vietnamese"
    INDIAN = "indian"
    MEXICAN = "mexican"
    FRENCH = "french"
    SPANISH = "spanish"
    BBQ = "bbq"
    SEAFOOD = "seafood"
    CAFE = "cafe"
    BAR = "bar"
    OTHER = "other"


class FeatureCode(str, Enum):
    PARKING = "parking"
    PETS_ALLOWED = "pets_allowed"
    KIDS_MENU = "kids_menu"
    GROUP_SEATING = "group_seating"
    PRIVATE_ROOM = "private_room"
    BABY_CHAIR = "baby_chair"
    WHEELCHAIR_ACCESS = "wheelchair_access"


class CuisineConstraint(BaseModel):
    code: CuisineCode
    strength: ConstraintStrength


class MenuConstraint(BaseModel):
    name: str = Field(min_length=1)
    strength: ConstraintStrength


class RestaurantRetrieval(BaseModel):
    cuisines: list[CuisineConstraint] = Field(default_factory=list)
    menus: list[MenuConstraint] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    excluded_themes: list[str] = Field(default_factory=list)
    occasion: str | None = None

    @field_validator("cuisines", "menus", "themes", "excluded_themes", mode="before")
    @classmethod
    def normalize_lists(cls, value):
        return [] if value is None else value


class RestaurantFilters(BaseModel):
    location: str | None = None
    radius_km: float | None = Field(default=None, gt=0, le=100)
    open_now: bool = False
    # GPT에게 요일 산술을 맡기지 않는다. 서버가 현재 날짜 기준으로 계산한다.
    visit_date_expression: str | None = None
    visit_time: str | None = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    party_size: int | None = Field(default=None, ge=1, le=100)
    min_rating: float | None = Field(default=None, ge=0, le=5)
    prefer_high_rating: bool = False
    budget_min_krw: int | None = Field(default=None, ge=0)
    budget_max_krw: int | None = Field(default=None, ge=0)
    required_features: list[FeatureCode] = Field(default_factory=list)
    preferred_features: list[FeatureCode] = Field(default_factory=list)
    excluded_features: list[FeatureCode] = Field(default_factory=list)

    @field_validator(
        "required_features", "preferred_features", "excluded_features", mode="before"
    )
    @classmethod
    def normalize_lists(cls, value):
        return [] if value is None else value

    @model_validator(mode="after")
    def validate_ranges(self):
        if (
            self.budget_min_krw is not None
            and self.budget_max_krw is not None
            and self.budget_min_krw > self.budget_max_krw
        ):
            raise ValueError("budget_min_krw must be <= budget_max_krw")
        return self


class RestaurantTaskV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    domain: str = Field(pattern=r"^restaurant$")
    retrieval: RestaurantRetrieval
    filters: RestaurantFilters


class TravelQueryV2(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(pattern=r"^2\.0$")
    language: str
    intent: str = Field(pattern=r"^single_place_recommendation$")
    weather_requested: bool = False
    original_question: str
    normalized_question: str
    tasks: list[RestaurantTaskV2] = Field(min_length=1, max_length=1)


SYSTEM_PROMPT = """
당신은 SeoulMate의 식당 단일 추천용 Structured Query Parser입니다.
답변을 만들지 말고 TravelQueryV2만 반환하세요.

[고정 계약]
- schema_version은 "2.0"입니다.
- intent는 single_place_recommendation입니다.
- restaurant Task는 정확히 1개입니다.
- 추천 개수, RAG 후보 개수, GPT 최종 선택 개수는 추출하지 않습니다. 서버가 결정합니다.
- language는 번역 결과가 아니라 사용자 원문의 언어입니다.
- source_mode는 반환하지 않습니다. 서버가 날짜 표현과 weather_requested로 결정합니다.
- weather_requested는 사용자가 비·눈·더위·추위·날씨를 명시했을 때만 true입니다.
- "지금 영업 중"은 영업 필터일 뿐 날씨 요청이 아니므로 weather_requested=false입니다.
- 질문에 없는 조건을 만들지 않습니다.

[Retrieval]
- cuisines는 언어 중립 CuisineCode로 반환합니다.
- 음식군은 기본적으로 required입니다. 음식군 바로 주변에 "이면 좋아", "선호",
  "가능하면", "prefer", "would prefer" 같은 명시적 완화 표현이 있을 때만 preferred입니다.
- "태국 음식점 추천", "Find a Chinese restaurant"는 required입니다.
- 구체 음식·메뉴명(예: 마라탕, 냉면, 파스타)은 반드시 menus에 넣습니다.
- "먹고 싶어/파는 곳/with 메뉴"는 required이고 "있으면 좋아"만 preferred입니다.
- themes는 조용함, 분위기, 데이트, 대화하기 편함 같은 의미 검색 조건입니다.
- 원문에서 피한 분위기는 excluded_themes에 넣습니다.
- 위치·날짜·시간·평점·가격·거리·시설은 themes에 절대 넣지 않습니다.

[Filters]
- location에는 지역명만 넣습니다.
- radius_km는 사용자가 숫자로 명시했을 때만 넣습니다.
- open_now는 지금/현재 영업 중을 명시했을 때만 true입니다.
- visit_date_expression에는 원문의 날짜 표현을 그대로 넣습니다. 예: "내일", "이번 토요일",
  "2026-07-18". 날짜 계산은 하지 않습니다. 날짜 표현이 없으면 null입니다.
- visit_time은 반드시 HH:MM입니다. 아침=09:00, 점심=12:00, 오후=15:00,
  저녁=19:00, 밤=21:00을 사용하되 명시 시각이 있으면 그 시각을 사용합니다.
- min_rating은 숫자 최저 평점이 있을 때만 넣습니다.
- "평점 좋은/높은/highly rated"처럼 숫자가 없으면 min_rating은 null,
  prefer_high_rating은 true입니다.
- 가격은 원 단위 정수입니다.
- 시설은 FeatureCode만 사용합니다.
- 시설 매핑: 주차=parking, 반려동물/애견 동반=pets_allowed,
  단체석=group_seating, 룸/개별실/private room=private_room,
  휠체어/무장애=wheelchair_access, 아기의자=baby_chair입니다.
- "가능한", "함께 갈 수 있는", "모두 있는", "with"는 required_features입니다.
- 시설 표현은 themes에 넣지 않습니다.
- "주차는 없어도 괜찮다"처럼 필수가 아니라는 표현은 required/preferred/excluded 어디에도 넣지 않습니다.
- "일식이면 좋아"는 required가 아니라 preferred입니다.

[판정 예시]
- "반려동물과 함께 갈 수 있는 식당" → required_features=[pets_allowed]
- "단체석과 룸이 모두 있는 식당" → required_features=[group_seating, private_room]
- "마라탕 먹고 싶어" → menus=[{{name:"마라탕", strength:"required"}}]
- "주차는 없어도 괜찮아" → 주차를 어떤 feature 목록에도 넣지 않음
- "평점 좋은 태국 음식점" → thai required, prefer_high_rating=true, themes에는 평점을 넣지 않음

[중복 금지]
- 날씨 요청 객체는 만들지 않습니다. 날씨 위치·시각은 filters에서 서버가 동일하게 사용합니다.
- search_query 문자열은 만들지 않습니다. 서버가 retrieval의 구조화된 값을 조합합니다.
"""

HUMAN_PROMPT = """
[현재 날짜]
{today}

[사용자 질문]
{question}

TravelQueryV2로 구조화하세요.
"""


CASES = [
    {
        "question": "홍대에서 중식당을 찾고 있어. 평점 4.5 이상이고 1인 메뉴 가격은 3만원 이하였으면 좋겠어.",
        "expect": {"cuisine": ["chinese", "required"], "min_rating": 4.5, "budget_max": 30000},
    },
    {
        "question": "지금 강남역 반경 2km 안에서 영업 중이고 주차 가능한 한식당 추천해줘.",
        "expect": {"cuisine": ["korean", "required"], "radius": 2.0, "open_now": True, "required": ["parking"]},
    },
    {
        "question": "내일 저녁 성수에서 반려동물과 함께 갈 수 있는 조용한 이탈리안 식당을 찾고 있어.",
        "expect": {"cuisine": ["italian", "required"], "date": "2026-07-15", "time": "19:00", "required": ["pets_allowed"], "theme": "조용"},
    },
    {
        "question": "이번 토요일 오후 3시에 종로에서 휠체어 접근이 가능한 식당을 추천해줘. 일식이면 좋아.",
        "expect": {"cuisine": ["japanese", "preferred"], "date": "2026-07-18", "time": "15:00", "required": ["wheelchair_access"]},
    },
    {
        "question": "을지로에서 모임할 거야. 단체석과 룸이 모두 있는 식당으로 부탁하고 예산은 2만원에서 5만원 사이야.",
        "expect": {"budget_min": 20000, "budget_max": 50000, "required": ["group_seating", "private_room"]},
    },
    {
        "question": "Find a quiet Chinese restaurant within 3 km of Hongdae, rated 4.3 or higher, with parking.",
        "expect": {"language": "en", "cuisine": ["chinese", "required"], "radius": 3.0, "min_rating": 4.3, "required": ["parking"]},
    },
    {
        "question": "홍대에서 마라탕 먹고 싶어. 시끄러운 술집 말고 대화하기 편한 식당이면 좋겠어.",
        "expect": {"menu": ["마라탕", "required"], "theme": "대화", "excluded_theme": "시끄"},
    },
    {
        "question": "주차는 없어도 괜찮아. 서울에서 평점 좋은 태국 음식점 추천해줘.",
        "expect": {"cuisine": ["thai", "required"], "prefer_high_rating": True, "required": [], "neutral": ["parking"]},
    },
]


def normalize_execution_query(parsed: TravelQueryV2) -> dict:
    """LLM 의미 추출 뒤 원문으로 검증 가능한 값은 결정적으로 교정한다."""
    task = parsed.tasks[0]
    filters = task.filters.model_copy(deep=True)
    text = parsed.original_question.lower()
    base = date(2026, 7, 14)

    visit_date: date | None = None
    if "모레" in text or "day after tomorrow" in text:
        visit_date = base + timedelta(days=2)
    elif "내일" in text or "tomorrow" in text:
        visit_date = base + timedelta(days=1)
    elif "오늘" in text or "today" in text:
        visit_date = base
    else:
        weekdays = {
            "월요일": 0, "화요일": 1, "수요일": 2, "목요일": 3,
            "금요일": 4, "토요일": 5, "일요일": 6,
            "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
            "friday": 4, "saturday": 5, "sunday": 6,
        }
        for label, weekday in weekdays.items():
            if label in text:
                visit_date = base + timedelta(days=(weekday - base.weekday()) % 7)
                break
        if visit_date is None:
            explicit = re.search(r"\b(20\d{2})[-./](\d{1,2})[-./](\d{1,2})\b", text)
            if explicit:
                visit_date = date(*(int(value) for value in explicit.groups()))

    optional_feature_contexts = {
        FeatureCode.PARKING: ("주차", "parking"),
        FeatureCode.PETS_ALLOWED: ("반려동물", "애견", "pets"),
    }
    optional_words = ("없어도", "상관없", "괜찮", "not required", "don't need", "is fine")
    for feature, keywords in optional_feature_contexts.items():
        if any(keyword in text for keyword in keywords) and any(word in text for word in optional_words):
            filters.required_features = [item for item in filters.required_features if item != feature]
            filters.preferred_features = [item for item in filters.preferred_features if item != feature]
            filters.excluded_features = [item for item in filters.excluded_features if item != feature]

    # "1인 메뉴 가격"은 party_size가 아니다. N명/party of N처럼 인원 표현만 신뢰한다.
    party_match = re.search(r"(\d+)\s*명", text) or re.search(r"party\s+of\s+(\d+)", text)
    filters.party_size = int(party_match.group(1)) if party_match else None
    if filters.min_rating is not None:
        filters.prefer_high_rating = False

    return {
        "source_mode": "rag_mcp" if parsed.weather_requested or visit_date else "rag_only",
        "visit_date": visit_date.isoformat() if visit_date else None,
        "task": task,
        "filters": filters,
    }


def validate_case(parsed: TravelQueryV2, expected: dict) -> tuple[list[str], dict]:
    execution = normalize_execution_query(parsed)
    task = parsed.tasks[0]
    retrieval, filters = task.retrieval, execution["filters"]
    errors: list[str] = []
    cuisines = {(item.code.value, item.strength.value) for item in retrieval.cuisines}
    menus = {(item.name.lower(), item.strength.value) for item in retrieval.menus}
    required = {item.value for item in filters.required_features}
    if "language" in expected and parsed.language != expected["language"]:
        errors.append(f"language={parsed.language}")
    if "cuisine" in expected and tuple(expected["cuisine"]) not in cuisines:
        errors.append(f"cuisines={sorted(cuisines)}")
    if "menu" in expected and tuple(expected["menu"]) not in menus:
        errors.append(f"menus={sorted(menus)}")
    checks = {
        "radius": filters.radius_km,
        "open_now": filters.open_now,
        "date": execution["visit_date"],
        "time": filters.visit_time,
        "min_rating": filters.min_rating,
        "prefer_high_rating": filters.prefer_high_rating,
        "budget_min": filters.budget_min_krw,
        "budget_max": filters.budget_max_krw,
    }
    for key, actual in checks.items():
        if key in expected and actual != expected[key]:
            errors.append(f"{key}={actual}")
    if "required" in expected and required != set(expected["required"]):
        errors.append(f"required={sorted(required)}")
    if "neutral" in expected:
        all_features = {
            *(item.value for item in filters.required_features),
            *(item.value for item in filters.preferred_features),
            *(item.value for item in filters.excluded_features),
        }
        leaked = set(expected["neutral"]) & all_features
        if leaked:
            errors.append(f"neutral_features_leaked={sorted(leaked)}")
    if "theme" in expected and not any(expected["theme"] in value for value in retrieval.themes):
        errors.append(f"themes={retrieval.themes}")
    if "excluded_theme" in expected and not any(
        expected["excluded_theme"] in value for value in retrieval.excluded_themes
    ):
        errors.append(f"excluded_themes={retrieval.excluded_themes}")
    return errors, execution


async def main(full: bool) -> None:
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    chain = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT), ("human", HUMAN_PROMPT)
    ]) | ChatOpenAI(model=model, temperature=0).with_structured_output(
        TravelQueryV2,
        method="json_schema",
        strict=True,
    )
    results = await asyncio.gather(*[
        chain.ainvoke({"today": "2026-07-14", "question": case["question"]})
        for case in CASES
    ])
    reports = []
    for case, parsed in zip(CASES, results):
        errors, execution = validate_case(parsed, case["expect"])
        reports.append({
            "question": case["question"],
            "ok": not errors,
            "errors": errors,
            "derived_source_mode": execution["source_mode"],
            "normalized_visit_date": execution["visit_date"],
            "parsed": parsed.model_dump(mode="json") if full else None,
        })
    print(json.dumps({
        "model": model,
        "passed": sum(item["ok"] for item in reports),
        "total": len(reports),
        "cases": reports,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--full", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.full))
