"""물품보관함 REST API 및 MCP 응답 모델."""
from typing import Literal

from pydantic import BaseModel, Field


class StorageLocker(BaseModel):
    id: int
    main_location: str
    detail_location: str
    locker_count: int
    road_address: str
    jibun_address: str
    lat: float
    lng: float
    hours: str
    description: str
    fee: str
    payment_method: str
    overtime_unit: str


class StorageLockerSizeAvailability(BaseModel):
    large: int = Field(default=0, ge=0)
    medium: int = Field(default=0, ge=0)
    small: int = Field(default=0, ge=0)


class StorageLockerSummary(BaseModel):
    locker_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    main_location: str | None = None
    detail_location: str | None = None
    road_address: str | None = None
    lot_number_address: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    distance_meters: float = Field(ge=0)
    total_count: int = Field(ge=0)
    available_count: int = Field(ge=0)
    in_use_count: int = Field(ge=0)
    available_by_size: StorageLockerSizeAvailability
    observed_at: str | None = None
    source: Literal["public_data_portal"] = "public_data_portal"


class NearbyStorageLockersResult(BaseModel):
    query: str = Field(min_length=1)
    center_name: str = Field(min_length=1)
    center_latitude: float = Field(ge=-90, le=90)
    center_longitude: float = Field(ge=-180, le=180)
    radius_meters: float = Field(gt=0)
    lockers: list[StorageLockerSummary] = Field(default_factory=list)


class StorageLockerCompartmentDetail(BaseModel):
    detail_id: str | None = None
    kind: str | None = None
    name: str | None = None
    width: str | None = None
    depth: str | None = None
    height: str | None = None
    fee: str | None = None
    payment_method: str | None = None
    additional_fee_unit_time: str | None = None
    additional_fee: str | None = None
    control_method: str | None = None
    usage_method: str | None = None
    restricted_items: str | None = None


class StorageLockerDetail(BaseModel):
    locker_id: str = Field(min_length=1)
    municipality_code: str | None = None
    municipality_name: str | None = None
    name: str = Field(min_length=1)
    main_location: str | None = None
    detail_location: str | None = None
    road_address: str | None = None
    lot_number_address: str | None = None
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    total_count: int = Field(ge=0)
    available_count: int | None = Field(default=None, ge=0)
    in_use_count: int | None = Field(default=None, ge=0)
    available_by_size: StorageLockerSizeAvailability | None = None
    observed_at: str | None = None
    weekday_hours: str | None = None
    saturday_hours: str | None = None
    holiday_hours: str | None = None
    free_usage_time: str | None = None
    installed_on: str | None = None
    customer_center_phone: str | None = None
    managing_organization: str | None = None
    managing_organization_phone: str | None = None
    compartments: list[StorageLockerCompartmentDetail] = Field(
        default_factory=list
    )
    source: Literal["public_data_portal"] = "public_data_portal"
