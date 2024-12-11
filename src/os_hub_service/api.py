import os
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
API_KEY = os.getenv("Open_Supply_Hub_API_KEY")
BASE_URL = "https://staging.opensupplyhub.org/api"

if not API_KEY:
    raise ValueError("Open_Supply_Hub_API_KEY is not set in the environment.")

async def fetch_facilities(query: str = None):
    params = {"q": query} if query else {}
    headers = {"Authorization": f"Token {API_KEY}"}
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/facilities", params=params, headers=headers)
        response.raise_for_status()
        return response.json()