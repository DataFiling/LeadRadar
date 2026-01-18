import os
import re
import asyncio
from fastapi import FastAPI, Request, HTTPException
from playwright.async_api import async_playwright

# --- INITIALIZATION ---
app = FastAPI(title="LeadRadar Pro")
# Critical for avoiding 404s when RapidAPI or Railway adds/removes trailing slashes
app.router.redirect_slashes = False

# Limits concurrent browsers to protect Railway RAM
MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

# Regex for technographics and contact mining
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I)

# --- 1. THE HEARTBEAT ---
@app.get("/")
async def health_check():
    """Confirms the Watcher is active in Lost Jerusalem."""
    return {"status": "LeadRadar Online", "version": "2026.1.07"}

# --- 2. THE WATCHER ENGINE ---
async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        # Browser is already installed via Dockerfile
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Determine if we are doing a Tech Stack scan or a Real Estate Zip scan
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            # Navigate to the Apophenic Substrate (the target site)
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(2) # Allow JS to settle
            html = await page.content()
            
            leads = []
            if is_zip:
                # Targeted scraping for Real Estate leads
                cards = await page.query_selector_all("[data-testid='property-card']")
                for card in cards[:10]:
                    addr = await card.query_selector("[data-label='pc-address']")
                    price = await card.query_selector("[data-label='pc-price']")
                    if addr and price:
                        leads.append({
                            "address": (await addr.inner_text()).strip(),
                            "price": (await price.inner_text()).strip()
                        })

            # General signal mining
            hiring = any(word in html.lower() for word in ["careers", "hiring", "job-openings"])
            emails = list(set(EMAIL_PATTERN.findall(html)))[:3]
            
            await browser.close()
            return {
                "url": url,
                "hiring_signal": hiring,
                "contacts": {"emails": emails},
                "real_estate_leads": leads if is_zip else None,
                "status": "success"
            }
        except Exception as e:
            await browser.close()
            return {"error": "Observation failed", "details": str(e)}

# --- 3. THE ENDPOINTS ---

@app.get("/leads/{zip_code}")
@app.get("/leads/{zip_code}/")
async def zip_leads_endpoint(zip_code: str, request: Request):
    """Path-based route for Real Estate Lead Enrichment."""
    # Security check against the Secret set in Railway Variables
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized Agent")

    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(zip_code, is_zip=True)

@app.get("/analyze")
async def analyze_endpoint(url: str, request: Request):
    """Query-based route for Technographics and Sentiment."""
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized Agent")

    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(url, is_zip=False)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
