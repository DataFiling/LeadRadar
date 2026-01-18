import os
import re
import asyncio
from fastapi import FastAPI, Request, HTTPException
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro")
# Critical: This stops FastAPI from redirecting /leads/90210 to /leads/90210/
app.router.redirect_slashes = False 

MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

# --- DEBUG MIDDLEWARE ---
@app.middleware("http")
async def trace_404(request: Request, call_next):
    response = await call_next(request)
    if response.status_code == 404:
        print(f"WATCHER ALERT: 404 on path -> {request.url.path}")
    return response

# --- 1. HEARTBEAT ---
@app.get("/")
async def health_check():
    return {"status": "LeadRadar Online", "version": "2026.1.08"}

# --- 2. THE WATCHER ENGINE ---
async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()
        
        # Real Estate Search (Stale Listings) or Standard Analyze
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
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

# Using explicit paths to catch both slash variants
@app.get("/leads/{zip_code}")
@app.get("/leads/{zip_code}/")
async def zip_leads_endpoint(zip_code: str, request: Request):
    # Check X-RapidAPI-Proxy-Secret variable in Railway
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized")

    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(zip_code, is_zip=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
