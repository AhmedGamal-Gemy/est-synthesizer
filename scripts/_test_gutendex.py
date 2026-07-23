"""Quick Gutendex connectivity test."""
import asyncio
import httpx
from backend.app.config import settings

async def test():
    url = f"{settings.GUTENDEX_BASE_URL}?search=science&languages=en"
    print(f"URL: {url}")
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.get(url)
        print(f"Status: {r.status_code}")
        data = r.json()
        print(f"Count: {data['count']}")
        if data["count"] > 0:
            print(f"First book: {data['results'][0]['title']}")

asyncio.run(test())
