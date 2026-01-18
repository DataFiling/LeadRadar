import os
import re
import asyncio
import subprocess
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from playwright.async_api import async_playwright

# --- INITIALIZATION ---
# This ensures the browser is ready on Railway's Linux environment
try:
    subprocess.run(["playwright", "install", "--with-deps", "chromium"], check=True)
except Exception as e:
    print(f"Browser check: {e}")

app = FastAPI(title="LeadRadar Pro")

# --- GLOBAL CONFIG & GUARDS ---
# Semaphore: Limits to 3 browsers at once to protect your Railway RAM
MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

# Regex for data extraction
SOCIAL_PATTERNS = {
    "LinkedIn": re.compile(r"linkedin\.com/(company|in)/[a-z0-9\-_]+", re.I),
    "X_Twitter": re.compile(r"(twitter\.com|x\.com)/[a-z0-9\-_]+", re.I),
    "Instagram": re.compile(r"instagram\.com/[a-z0-9\-_]+", re.I)
}
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I)

# --- 1. THE HEARTBEAT (Fixes Railway Healthcheck Failures) ---
@app.get("/")
async def health_check():
    """Tells Railway the Watcher is alive and well."""
    return {
        "status": "LeadRadar Online",
        "version": "2026.1",
        "mode": "High Performance (Optimized)"
    }

# --- 2. BANDWIDTH PROTECTOR ---
async def intercept_route(route):
    """Aborts heavy assets. This turns a 10MB page into a 300KB data-only load."""
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()

# --- 3. THE WATCHER ENGINE ---
async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Apply data savings and stealth
        await page.route("**/*", intercept_route)
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2) # Allow JS to populate the text
            html = await page.content()
            
            # --- SCRAPE LOGIC ---
            leads = []
            if is_zip:
                # Target property cards specifically for Real Estate Arbitrage
                cards = await page.query_selector_all("[data-testid='property-card']")
                for card in cards[:10]:
                    addr_el = await card.query_selector("[data-label='pc-address']")
                    pri_el = await card.query_selector("[data-label='pc-price']")
                    if addr_el and pri_el:
                        leads.append({
                            "address": (await addr_el.inner_text()).strip(),
                            "price": (await pri_el.inner_text()).strip(),
                            "days_on_market": "Found" # Logic for DOM can be expanded here
                        })

            # Business Signal Extraction
            tech_found = []
            if "shopify" in html.lower(): tech_found.append({"name": "Shopify", "category": "E-commerce"})
            if "facebook.net" in html.lower(): tech_found.append({"name": "Meta Pixel", "category": "Advertising"})
            
            hiring = any(word in html.lower() for word in ["careers", "hiring", "job-openings"])
            emails = list(set(EMAIL_PATTERN.findall(html)))[:3]
            socials = {k: v.search(html).group(0) for k, v in SOCIAL_PATTERNS.items() if v.search(html)}

            # Scoring
            score = (len(tech_found) * 15) + (35 if hiring else 0) + (len(socials) * 5)
            
            await browser.close()
            return {
                "url": url,
                "lead_score": min(score, 100),
                "hiring_signal": hiring,
                "tech_stack": tech_found,
                "social_profiles": socials,
                "contacts": {"emails": emails},
                "real_estate_leads": leads if is_zip else None,
                "status": "success"
            }
        except Exception as e:
            await browser.close()
            return {"error": "Observation failed", "details": str(e)}

# --- 4. API ENDPOINTS ---

@app.get("/analyze")
async def analyze_endpoint(url: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(url, is_zip=False)

# Catch-all for /leads to prevent 404s when zip is missing
@app.get("/leads")
async def leads_no_zip():
    return {"error": "Missing Zip Code", "usage": "GET /leads/90210"}

# The main Path-Parameter route for Real Estate
@app.get("/leads/{zip_code}")
async def zip_leads_endpoint(zip_code: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(zip_code, is_zip=True)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
