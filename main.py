import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro")
# Prevents automatic redirects that confuse RapidAPI proxies
app.router.redirect_slashes = False

MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

@app.get("/")
async def health_check():
    """Confirms the Watcher is active."""
    return {"status": "LeadRadar Online", "version": "2026.1.10"}

async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        context = await browser.new_context()
        page = await context.new_page()
        
        # Realtor.com targeted search for 'Stale' Real Estate Listings
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2) 
            html = await page.content()
            
            leads = []
            if is_zip:
                # Scrape property cards for the $15 lead tier
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
            return {"error": "Observation failed", "details": str(e)}

# --- THE SPECIFIC ROUTE ---
@app.get("/leads/{zip_code}")
async def zip_leads_endpoint(zip_code: str, request: Request):
    # Verify the Secret from Railway Variables
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized Agent"})
    return await run_lead_radar(zip_code, is_zip=True)

# --- THE CATCH-ALL DEBUG (This stops the 404) ---
@app.api_route("/{path_name:path}", methods=["GET"])
async def catch_all(request: Request, path_name: str):
    return {
        "error": "Path Not Found",
        "received_path": path_name,
        "hint": "If you meant to use /leads/90210, ensure no double slashes are present."
    }
