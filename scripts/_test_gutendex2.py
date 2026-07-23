"""Test the exact URL the scraper uses."""
import asyncio
import httpx

async def test():
    url = "https://gutendex.com/books?languages=en&mime_type=text/plain&search=science"
    print(f"URL: {url}")
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
        resp = await client.get(url)
        print(f"Status: {resp.status_code}")
        print(f"URL after redirects: {resp.url}")
        data = resp.json()
        print(f"Count: {data['count']}")

asyncio.run(test())
