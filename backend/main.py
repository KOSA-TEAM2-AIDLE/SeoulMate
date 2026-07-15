from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# from dotenv import load_dotenv
# from core.config import ALLOWED_ORIGINS

from core.config import settings
from api.routers import (
    accommodations,
    actions,
    cafes,
    chat,
    events,
    health,
    places,
    restaurants,
    routes,
    storage_lockers,
    tools,
    travel_query,
    weather,
)

# load_dotenv() # Pydantic Settings 설정으로 인해 제외 -> Settings 가 직접 .env를 읽음

app = FastAPI(title="SeoulMate Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 명세서 2장 엔드포인트 전체 목록 참고. 명세서상 base path prefix 없음.
app.include_router(health.router)
app.include_router(tools.router)
app.include_router(places.router)
app.include_router(actions.router)
app.include_router(chat.router)
app.include_router(cafes.router)
app.include_router(restaurants.router)
app.include_router(accommodations.router)
app.include_router(events.router)
app.include_router(storage_lockers.router)
app.include_router(weather.router)
app.include_router(routes.router)
app.include_router(travel_query.router)


@app.get("/")
def read_root():
    return {"message": "FastAPI Server is running!"}
