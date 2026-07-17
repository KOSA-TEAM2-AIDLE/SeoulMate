import asyncio
import json
import httpx

async def main():
    async with httpx.AsyncClient() as client:
        req = {
            "message": "7/17~7/18 예약가능한 강남 호텔 추천해줘",
            "lang": "ko"
        }
        async with client.stream("POST", "http://127.0.0.1:8000/chat", json=req) as response:
            async for line in response.aiter_lines():
                if line:
                    print(line)

asyncio.run(main())
