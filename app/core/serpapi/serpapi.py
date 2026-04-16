
import requests
from app.config import SERPAPI_KEY

def search_with_serpapi(query: str):
    url = "https://serpapi.com/search"
    params = {
        "engine": "google",
        "q": query,
        "api_key": SERPAPI_KEY
    }
    res = requests.get(url, params=params)
    data = res.json()

    results = []
    if "organic_results" in data:
        for item in data["organic_results"][:5]:
            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet")
            })
    return results