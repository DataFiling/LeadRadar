import os
import re
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro")
app.router.redirect_slashes = False

MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

# --- 1. THE "GHOST" CATCHER (Middleware to fix 404s) ---
@app.middleware("http")
async def fix_double_slashes(request: Request, call_next):
    # This detects if RapidAPI is sending //leads instead of /leads
    path = request.url.path
    if "//" in path:
        new_path = path.replace("//", "/")
        print(f"DEBUG: Redirecting double slash {path} to {new_path}")
        # We don't redirect (which causes 404s in proxies), we just update the scope
        request.scope["path"] = new_path
    
    response = await call_next(request)
    return response

# --- 2. HEARTBEAT ---
@app.get("/")
async def health_check():
    return {"status": "LeadRadar Online", "version": "2026.1.09"}

# --- 3. THE WATCHER ENGINE ---
async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        # Pre-installed via Dockerfile
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()
        
        # Target: Realtor.com for Stale Real Estate Listings
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

# --- 4. THE ENDPOINTS ---

@app.get("/leads/{zip_code}")
async def zip_leads_endpoint(zip_code: str, request: Request):
    # Security: Check against Railway Variable
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized Agent"})

    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(zip_code, is_zip=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
