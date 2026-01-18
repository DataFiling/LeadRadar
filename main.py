import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

# --- INITIALIZATION ---
# We keep this as simple as possible to ensure the health check passes immediately.
app = FastAPI(title="LeadRadar Pro")

# This helps avoid issues with trailing slashes from different proxies
app.router.redirect_slashes = False

# Limit to 3 concurrent scans to stay within Railway's RAM limits (preventing crashes)
MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

# --- 1. HEARTBEAT (The Health Check) ---
@app.get("/")
async def health_check():
    """
    Railway pings this. If it returns 200, the deployment succeeds.
    """
    return {
        "status": "LeadRadar Online",
        "version": "2.0.0",
        "environment": "Docker/Railway"
    }

# --- 2. THE WATCHER ENGINE ---
async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        # We do NOT run install commands here; the Dockerfile already did that.
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Build the URL: If zip, use Realtor; if not, use the raw URL
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            # The 'Watcher' enters the Apophenic Substrate (the target site)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2) 
            
            leads = []
            if is_zip:
                # Scrape for 'Stale' Real Estate Listings
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
            return {
                "url": url,
                "real_estate_leads": leads,
                "status": "success"
            }
        except Exception as e:
            await browser.close()
            return {"error": "Observation failed", "details": str(e)}

# --- 3. THE ENDPOINTS (The Logic) ---

@app.get("/leads/{zip_code}")
@app.get("/leads/{zip_code}/")
async def zip_leads_endpoint(zip_code: str, request: Request):
    """
    Main Real Estate route. Note the dual decorators to prevent 404s.
    """
    # Security: Verify the Signal from the Watchers (RapidAPI)
    secret = request.headers.get("X-RapidAPI-Proxy-Secret")
    if secret != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized Agent"})

    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(zip_code, is_zip=True)

# --- 4. DEBUG CATCH-ALL ---
@app.api_route("/{path_name:path}", methods=["GET"])
async def catch_all(request: Request, path_name: str):
    """
    If you get a 404, this route will catch it and tell us why.
    """
    return {
        "error": "Path Not Found",
        "received_path": f"/{path_name}",
        "hint": "Check your Base URL in RapidAPI. It should NOT have a trailing slash."
    }

if __name__ == "__main__":
    import uvicorn
    # Respect the PORT variable provided by Railway
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
