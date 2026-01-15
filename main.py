import os
import re
import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from bs4 import BeautifulSoup

app = FastAPI(title="LeadRadar Unified API")

# --- SECURITY CONFIG ---
# This matches the secret you will set in Railway and RapidAPI
PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET", "default_secret_for_local_test")

async def verify_rapidapi(x_rapidapi_proxy_secret: str = Header(None)):
    if x_rapidapi_proxy_secret != PROXY_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized: Secret Mismatch")

# --- SIGNATURE DATABASES ---
TECH_SIGNATURES = {
    "E-commerce": {"Shopify": r"cdn\.shopify\.com", "WooCommerce": r"woocommerce"},
    "Analytics": {"Google Analytics": r"googletagmanager", "Meta Pixel": r"facebook\.net"},
    "Marketing": {"HubSpot": r"js\.hs-scripts\.com", "Klaviyo": r"static\.klaviyo\.com"}
}

HIRING_KEYWORDS = ["hiring", "careers", "open roles", "join our team", "vacancies"]

# --- CORE LOGIC ---

async def perform_scan(url: str):
    if not url.startswith("http"):
        url = f"https://{url}"
        
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            # 1. Fetch Page
            response = await client.get(url)
            html = response.text.lower()
            headers = str(response.headers).lower()
            combined = html + headers

            # 2. Technographics (#8)
            tech = []
            for cat, techs in TECH_SIGNATURES.items():
                for name, pat in techs.items():
                    if re.search(pat, combined):
                        tech.append({"name": name, "category": cat})

            # 3. Hiring Signals (#4)
            hiring = any(word in combined for word in HIRING_KEYWORDS)

            # 4. StockWatch (#10)
            stockout = any(word in html for word in ["out of stock", "sold out", "unavailable"])

            return {
                "url": url,
                "tech_stack": tech,
                "hiring_signal": hiring,
                "stockwatch_alert": stockout,
                "status": "success"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "LeadRadar Online"}

@app.get("/analyze")
async def analyze(url: str, _ = Depends(verify_rapidapi)):
    result = await perform_scan(url)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result
