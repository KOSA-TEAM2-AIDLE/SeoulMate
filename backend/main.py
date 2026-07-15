from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from core.config import ALLOWED_ORIGINS
from api.routers import (
    health,
    tools,
    places,
    actions,
    chat,
    cafes,
    restaurants,
    accommodations,
    attractions,
    storage_lockers,
    weather,
    routes,
)

load_dotenv()

app = FastAPI(title="SeoulMate Backend API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
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
app.include_router(attractions.router)
app.include_router(storage_lockers.router)
app.include_router(weather.router)
app.include_router(routes.router)


@app.get("/")
def read_root():
    return {"message": "FastAPI Server is running!"}
