import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro")
app.router.redirect_slashes = False

# Limits concurrent browsers to protect Railway RAM
MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

# --- 1. HEARTBEAT (Instant response for Railway) ---
@app.get("/")
async def health_check():
    """ railway pings this to confirm the service is healthy """
    return {"status": "LeadRadar Online", "version": "2.0.1"}

# --- 2. THE WATCHER ENGINE ---
async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        # Browser is pre-installed via Dockerfile
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()
        
        # Scrape Realtor.com for 'Stale' Real Estate Listings [cite: 2026-01-14]
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2) 
            
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
@app.get("/leads/{zip_code}/")
async def zip_leads_endpoint(zip_code: str, request: Request):
    # Verify the Secret from Railway Variables
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized"})

    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(zip_code, is_zip=True)

# --- 4. DEBUG CATCH-ALL (Diagnoses 404s) ---
@app.api_route("/{path_name:path}", methods=["GET"])
async def catch_all(request: Request, path_name: str):
    """ If you hit this, the path you're using doesn't match the routes above """
    return {
        "error": "Path Not Found",
        "received_path": f"/{path_name}",
        "hint": "Check if your Base URL in RapidAPI has an extra trailing slash."
    }
