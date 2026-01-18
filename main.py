import os
import re
import asyncio
import subprocess
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from playwright.async_api import async_playwright

# --- INITIALIZATION ---
# Pre-installing browser for Railway's Linux environment
try:
    subprocess.run(["playwright", "install", "--with-deps", "chromium"], check=True)
except Exception as e:
    print(f"Browser check: {e}")

# IMPORTANT: strict_slashes=False ensures that /leads/90210 and /leads/90210/ are identical
app = FastAPI(title="LeadRadar Pro")
app.router.redirect_slashes = False

# --- GLOBAL CONFIG & GUARDS ---
MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

SOCIAL_PATTERNS = {
    "LinkedIn": re.compile(r"linkedin\.com/(company|in)/[a-z0-9\-_]+", re.I),
    "X_Twitter": re.compile(r"(twitter\.com|x\.com)/[a-z0-9\-_]+", re.I),
    "Instagram": re.compile(r"instagram\.com/[a-z0-9\-_]+", re.I)
}
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I)

# --- 1. THE HEARTBEAT (Fixes Railway Healthcheck) ---
@app.get("/")
async def health_check():
    return {
        "status": "LeadRadar Online",
        "version": "2026.1",
        "mode": "High Performance"
    }

# --- 2. BANDWIDTH PROTECTOR ---
async def intercept_route(route):
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
        
        await page.route("**/*", intercept_route)
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Lost Jerusalem Property Search or Standard Analyze
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2) 
            html = await page.content()
            
            leads = []
            if is_zip:
                cards = await page.query_selector_all("[data-testid='property-card']")
                for card in cards[:10]:
                    addr_el = await card.query_selector("[data-label='pc-address']")
                    pri_el = await card.query_selector("[data-label='pc-price']")
                    if addr_el and pri_el:
                        leads.append({
                            "address": (await addr_el.inner_text()).strip(),
                            "price": (await pri_el.inner_text()).strip()
                        })

            tech_found = []
            if "shopify" in html.lower(): tech_found.append({"name": "Shopify", "category": "E-commerce"})
            
            hiring = any(word in html.lower() for word in ["careers", "hiring", "job-openings"])
            emails = list(set(EMAIL_PATTERN.findall(html)))[:3]
            socials = {k: v.search(html).group(0) for k, v in SOCIAL_PATTERNS.items() if v.search(html)}

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
@app.get("/analyze/")
async def analyze_endpoint(url: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(url, is_zip=False)

# THE FIX: Dual-route mapping for zip codes
@app.get("/leads/{zip_code}")
@app.get("/leads/{zip_code}/")
async def zip_leads_endpoint(zip_code: str, request: Request):
    # Verify the secret matches your Railway environment variable
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    
    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(zip_code, is_zip=True)

if __name__ == "__main__":
    # Ensure PORT is 8080 in Railway Variables
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
