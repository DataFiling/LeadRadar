import os
import re
import asyncio
import subprocess
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

# --- INITIALIZATION ---
try:
    subprocess.run(["playwright", "install", "--with-deps", "chromium"], check=True)
except Exception as e:
    print(f"Browser check: {e}")

app = FastAPI(title="LeadRadar Pro")

# --- GLOBAL CONFIG ---
MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)
SOCIAL_PATTERNS = {
    "LinkedIn": re.compile(r"linkedin\.com/(company|in)/[a-z0-9\-_]+", re.I),
    "X_Twitter": re.compile(r"(twitter\.com|x\.com)/[a-z0-9\-_]+", re.I),
    "Instagram": re.compile(r"instagram\.com/[a-z0-9\-_]+", re.I)
}
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I)

# --- 1. THE EMERGENCY CATCH-ALL (Fixes 404 Confusion) ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """If a 404 happens, this middleware will catch it and tell us the truth."""
    response = await call_next(request)
    if response.status_code == 404:
        print(f"DEBUG 404: The server received a request for: {request.url.path}")
    return response

@app.get("/")
async def health_check():
    return {"status": "LeadRadar Online", "version": "2026.1.06"}

# --- 2. THE WATCHER ENGINE ---
async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()
        
        # Realtor.com search for "Stale" Real Estate Listings
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2) 
            html = await page.content()
            
            leads = []
            if is_zip:
                cards = await page.query_selector_all("[data-testid='property-card']")
                for card in cards[:10]:
                    addr = await card.query_selector("[data-label='pc-address']")
                    price = await card.query_selector("[data-label='pc-price']")
                    if addr and price:
                        leads.append({
                            "address": (await addr.inner_text()).strip(),
                            "price": (await price.inner_text()).strip()
                        })
            
            await browser.close()
            return {"url": url, "real_estate_leads": leads, "status": "success"}
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

# --- 3. THE ENDPOINTS ---

@app.get("/leads/{zip_code}")
async def zip_leads_endpoint(zip_code: str, request: Request):
    """
    Scrapes Realtor.com for geographic-specific leads.
    This is the 'Path' parameter route.
    """
    # Security Guard
    secret = request.headers.get("X-RapidAPI-Proxy-Secret")
    if secret != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized Agent"})

    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(zip_code, is_zip=True)

if __name__ == "__main__":
    # Ensure Railway variable PORT is set to 8080
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
