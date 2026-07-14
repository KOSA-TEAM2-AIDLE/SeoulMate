from typing import Literal, Self

from pydantic import BaseModel, Field, field_validator, model_validator


def _strip_required_text(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("필수 문자열은 비어 있을 수 없습니다.")
    return normalized


def _blank_to_none(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class ResolvedPlace(BaseModel):
    place_id: str = Field(min_length=1)
    place_name: str = Field(min_length=1)
    category_name: str | None = None
    category_group_code: str | None = None
    category_group_name: str | None = None
    phone: str | None = None
    address_name: str | None = None
    road_address_name: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    place_url: str | None = None
    source: Literal["kakao_local"] = "kakao_local"

    @field_validator("place_id", "place_name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator(
        "category_name",
        "category_group_code",
        "category_group_name",
        "phone",
        "address_name",
        "road_address_name",
        "place_url",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _blank_to_none(value)


class KakaoPlaceDocument(BaseModel):
    id: str = Field(min_length=1)
    place_name: str = Field(min_length=1)
    category_name: str | None = None
    category_group_code: str | None = None
    category_group_name: str | None = None
    phone: str | None = None
    address_name: str | None = None
    road_address_name: str | None = None
    x: float = Field(ge=-180, le=180)
    y: float = Field(ge=-90, le=90)
    place_url: str | None = None
    distance: str | None = None

    @field_validator("id", "place_name")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        return _strip_required_text(value)

    @field_validator(
        "category_name",
        "category_group_code",
        "category_group_name",
        "phone",
        "address_name",
        "road_address_name",
        "place_url",
        "distance",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        return _blank_to_none(value)

    def to_resolved_place(self) -> ResolvedPlace:
        return ResolvedPlace(
            place_id=self.id,
            place_name=self.place_name,
            category_name=self.category_name,
            category_group_code=self.category_group_code,
            category_group_name=self.category_group_name,
            phone=self.phone,
            address_name=self.address_name,
            road_address_name=self.road_address_name,
            latitude=self.y,
            longitude=self.x,
            place_url=self.place_url,
        )


class PlaceResolutionResult(BaseModel):
    query: str = Field(min_length=1)
    selected: ResolvedPlace | None = None
    candidates: list[ResolvedPlace] = Field(default_factory=list)
    requires_disambiguation: bool = False

    @field_validator("query")
    @classmethod
    def validate_query(cls, value: str) -> str:
        return _strip_required_text(value)

    @model_validator(mode="after")
    def validate_selection_state(self) -> Self:
        candidate_ids = [candidate.place_id for candidate in self.candidates]
        if len(candidate_ids) != len(set(candidate_ids)):
            raise ValueError("장소 후보의 place_id는 중복될 수 없습니다.")

        if self.selected is not None:
            if self.requires_disambiguation:
                raise ValueError(
                    "선택된 장소가 있으면 모호성 확인을 요청할 수 없습니다."
                )
            if self.selected.place_id not in candidate_ids:
                raise ValueError(
                    "선택된 장소는 후보 목록에 포함되어야 합니다."
                )

        return self
