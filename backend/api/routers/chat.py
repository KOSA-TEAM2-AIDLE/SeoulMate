import json
import asyncio

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from schemas.chat import ChatDone, ChatMetaPlaces, ChatMetaRoute, ChatRequest, ChatToken
from application.travel_query.required_info import (
    ROUTE_MODIFICATION_UNSUPPORTED_MESSAGE,
)

router = APIRouter()

ROUTE_INTENTS = {"route_day", "route_multi", "route_edit"}
INTENT_MAP = {
    "single_place_recommendation": "rag",
    "day_trip_route": "route_day",
    "multi_day_route": "route_multi",
    "modify_route": "route_edit",
    "weather_information": "mcp",
    "general_response": "chitchat",
}

MOCK_TRAVEL_DATA = {
  "day": 1,
  "allDay": 3,
  "travelPath": {
    "1": [
      {
        "id": "ACCO001",
        "name": "L7 명동",
        "category": "숙소",
        "subCategory": "호텔",
        "address": "서울 중구 퇴계로 137",
        "lat": 37.5611,
        "lng": 126.9863,
        "rating": "4.5",
        "reviews": "1,824",
        "time": "11:00 (짐 보관)",
        "image": "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=150&q=80",
        "selectionReason": "명동역 바로 앞에 위치하여 대중교통 접근성이 뛰어나며, 본격적인 여행 시작 전 짐을 맡기기에 최적의 위치입니다."
      },
      {
        "id": "REST005",
        "name": "명동교자 본점",
        "category": "맛집",
        "subCategory": "한식/칼국수",
        "address": "서울 중구 명동10길 29",
        "lat": 37.5626,
        "lng": 126.9854,
        "rating": "4.6",
        "reviews": "5,842",
        "time": "12:00 - 13:00",
        "image": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=150&q=80",
        "selectionReason": "숙소에서 도보로 이동 가능한 명동의 대표 맛집으로, 깊은 맛의 칼국수와 마늘 겉절이로 든든한 첫 식사를 즐길 수 있습니다."
      },
      {
        "id": "SPOT001",
        "name": "경복궁",
        "category": "관광지",
        "subCategory": "역사/고궁",
        "address": "서울 종로구 사직로 161",
        "lat": 37.5796,
        "lng": 126.9770,
        "rating": "4.7",
        "reviews": "9,150",
        "time": "13:30 - 15:30",
        "image": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=150&q=80",
        "selectionReason": "서울을 대표하는 가장 웅장하고 아름다운 법궁으로, 고즈넉한 고궁 산책과 함께 한국의 역사적 정취를 느끼기 좋습니다."
      },
      {
        "id": "CAFE001",
        "name": "블루보틀 삼청 카페",
        "category": "카페",
        "subCategory": "스페셜티 커피",
        "address": "서울 종로구 북촌로5길 76",
        "lat": 37.5791,
        "lng": 126.9814,
        "rating": "4.4",
        "reviews": "1,204",
        "time": "16:00 - 17:00",
        "image": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=150&q=80",
        "selectionReason": "경복궁 관람 후 쉬어가기 좋은 위치에 있으며, 한옥과 현대적 미니멀리즘이 조화를 이룬 공간에서 스페셜티 커피를 맛볼 수 있습니다."
      },
      {
        "id": "SPOT004",
        "name": "청계천 광장",
        "category": "관광지",
        "subCategory": "도심/산책",
        "address": "서울 중구 태평로1가 1",
        "lat": 37.5691,
        "lng": 126.9787,
        "rating": "4.5",
        "reviews": "3,412",
        "time": "17:30 - 18:30",
        "image": "https://images.unsplash.com/photo-1578469550956-0e16b69c6a3d?auto=format&fit=crop&w=150&q=80",
        "selectionReason": "저녁 식사 전, 도심 속 흐르는 물소리를 들으며 여유롭게 하루 일정을 마무리하고 산책하기 좋은 코스입니다."
      }
    ],
    "2": [
      {
        "id": "REST002",
        "name": "우래옥",
        "category": "맛집",
        "subCategory": "평양냉면",
        "address": "서울 중구 창경궁로 62-29",
        "lat": 37.5684,
        "lng": 126.9995,
        "rating": "4.5",
        "reviews": "4,103",
        "time": "12:00 - 13:00",
        "image": "https://images.unsplash.com/photo-1552611052-33e04de081de?auto=format&fit=crop&w=150&q=80",
        "selectionReason": "오랜 역사와 전통을 자랑하는 서울의 대표 평양냉면 명가로, 깊고 진한 육향의 평양냉면을 경험할 수 있는 곳입니다."
      },
      {
        "id": "SPOT002",
        "name": "N서울타워",
        "category": "관광지",
        "subCategory": "전망대/랜드마크",
        "address": "서울 용산구 남산공원길 105",
        "lat": 37.5511,
        "lng": 126.9882,
        "rating": "4.5",
        "reviews": "8,402",
        "time": "14:00 - 16:30",
        "image": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&w=150&q=80",
        "selectionReason": "남산 정상에 우뚝 솟은 서울의 상징적인 랜드마크로, 서울 도심 전체를 한눈에 조망할 수 있는 최고의 뷰포인트입니다."
      },
      {
        "id": "CAFE003",
        "name": "명동 멧차",
        "category": "카페",
        "subCategory": "말차/티 하우스",
        "address": "서울 중구 명동9길 17",
        "lat": 37.5642,
        "lng": 126.9845,
        "rating": "4.3",
        "reviews": "641",
        "time": "17:00 - 18:00",
        "image": "https://images.unsplash.com/photo-1555507036-ab1f4038808a?auto=format&fit=crop&w=150&q=80",
        "selectionReason": "남산 투어를 마친 후 명동으로 돌아와, 맷돌로 직접 간 진한 말차 음료 및 디저트를 즐기며 차분한 휴식을 취하기에 좋습니다."
      }
    ]
  },
  "recommendList": [
    {
      "id": "ACCO003",
      "name": "신라호텔 서울",
      "category": "숙소",
      "subCategory": "럭셔리",
      "address": "서울 중구 동호로 249",
      "lat": 37.5559,
      "lng": 127.0051,
      "rating": "4.8",
      "reviews": "2,541",
      "time": "추천 숙소",
      "image": "https://images.unsplash.com/photo-1566073771259-6a8506099945?auto=format&fit=crop&w=150&q=80",
      "selectionReason": "세계적인 수준의 품격 있는 서비스와 남산 뷰를 누릴 수 있으며, 완벽한 호캉스와 미식 경험을 원하는 분께 추천하는 최고급 호텔입니다."
    },
    {
      "id": "REST010",
      "name": "진옥화할매원조닭한마리",
      "category": "맛집",
      "subCategory": "한식/닭요리",
      "address": "서울 종로구 종로40가길 14",
      "lat": 37.5703,
      "lng": 127.0062,
      "rating": "4.4",
      "reviews": "4,192",
      "time": "저녁 추천",
      "image": "https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=150&q=80",
      "selectionReason": "맑고 진한 닭 육수에 떡사리와 칼국수를 곁들여 먹는 동대문 골목의 전설적인 맛집으로, 하루의 피로를 풀어줄 따뜻하고 푸짐한 저녁 메뉴로 제격입니다."
    },
    {
      "id": "SPOT011",
      "name": "동대문디자인플라자 (DDP)",
      "category": "관광지",
      "subCategory": "랜드마크/전시",
      "address": "서울 중구 을지로 281",
      "lat": 37.5665,
      "lng": 127.0092,
      "rating": "4.6",
      "reviews": "7,321",
      "time": "오후/야경 추천",
      "image": "https://images.unsplash.com/photo-1538481199705-c710c4e965fc?auto=format&fit=crop&w=150&q=80",
      "selectionReason": "세계적인 건축가 자하 하디드가 설계한 미래지향적 건축물로, 밤이 되면 화려한 LED 불빛과 함께 독창적인 도시 야경을 선사합니다."
    },
    {
      "id": "CAFE005",
      "name": "대충유원지 인왕산",
      "category": "카페",
      "subCategory": "루프탑/뷰맛집",
      "address": "서울 종로구 필운대로 46",
      "lat": 37.5802,
      "lng": 126.9687,
      "rating": "4.5",
      "reviews": "423",
      "time": "전망 추천",
      "image": "https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=150&q=80",
      "selectionReason": "인왕산의 수려한 암벽 뷰와 서촌 골목의 고즈넉한 풍경을 한눈에 담으며 정갈하게 우려낸 차나 커피를 즐길 수 있는 전망 명소입니다."
    },
    {
      "id": "SPOT012",
      "name": "광장시장",
      "category": "관광지",
      "subCategory": "전통시장/먹거리",
      "address": "서울 종로구 창경궁로 88",
      "lat": 37.5701,
      "lng": 126.9998,
      "rating": "4.4",
      "reviews": "11,204",
      "time": "로컬 경험 추천",
      "image": "https://images.unsplash.com/photo-1552611052-33e04de081de?auto=format&fit=crop&w=150&q=80",
      "selectionReason": "육회, 녹두빈대떡, 마약김밥 등 서울의 대표적인 길거리 음식을 활기찬 시장 분위기 속에서 오감으로 즐길 수 있는 최고의 먹거리 명소입니다."
    }
  ]
}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def _stream(body: ChatRequest):
    if body.parsed_intent == "modify_route":
        meta = ChatMetaPlaces(intent="chitchat")
        yield _sse(meta.model_dump())
        yield _sse(
            ChatToken(
                text=ROUTE_MODIFICATION_UNSUPPORTED_MESSAGE
            ).model_dump()
        )
        yield _sse(ChatDone().model_dump())
        return

    intent = INTENT_MAP[body.parsed_intent]

    if intent in ROUTE_INTENTS:
        meta = ChatMetaRoute(intent=intent, days=[], total_days=0, total_places=0)
    else:
        meta = ChatMetaPlaces(intent=intent)

    meta_dict = meta.model_dump()
    meta_dict["type"] = "meta"
    yield _sse(meta_dict)

    welcome_text = (
        "안녕하세요! 요청하신 조건에 맞춰 멋진 서울 여행 코스를 구성해 보았습니다. "
        "지도에 새롭게 반영된 추천 일정을 지금 바로 확인해 보세요! 추가로 변경하고 싶은 부분이 있다면 편하게 말씀해 주세요."
        if body.lang == "ko" else
        "Hello! I have designed a wonderful Seoul travel itinerary based on your request. "
        "Please check the recommended schedule newly updated on the map! Feel free to let me know if there's anything else you'd like to adjust."
    )

    for word in welcome_text.split(" "):
        token_payload = ChatToken(text=word + " ").model_dump()
        token_payload["type"] = "token"
        yield _sse(token_payload)
        await asyncio.sleep(0.04)

    done_payload = ChatDone().model_dump()
    done_payload["type"] = "done"
    done_payload["data"] = MOCK_TRAVEL_DATA

    yield _sse(done_payload)


@router.post("/chat")
async def chat(body: ChatRequest):
    return StreamingResponse(_stream(body), media_type="text/event-stream")
