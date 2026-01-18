import os
import re
import asyncio
import subprocess
import uvicorn
from fastapi import FastAPI, Request, HTTPException
from playwright.async_api import async_playwright

# --- INITIALIZATION ---
try:
    # This ensures the browser binaries are installed on the Railway Linux container
    subprocess.run(["playwright", "install", "--with-deps", "chromium"], check=True)
except Exception as e:
    print(f"Browser check: {e}")

app = FastAPI(title="LeadRadar Pro")

# --- GLOBAL CONFIG & GUARDS ---
# Limit server to 3 concurrent browsers to stay within Railway RAM limits
MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

# Search Patterns
SOCIAL_PATTERNS = {
    "LinkedIn": re.compile(r"linkedin\.com/(company|in)/[a-z0-9\-_]+", re.I),
    "X_Twitter": re.compile(r"(twitter\.com|x\.com)/[a-z0-9\-_]+", re.I),
    "Instagram": re.compile(r"instagram\.com/[a-z0-9\-_]+", re.I)
}
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I)

# --- THE HEARTBEAT (Fixes Railway Healthcheck Failures) ---
@app.get("/")
async def health_check():
    """Tells Railway the service is healthy and ready to accept traffic."""
    return {
        "status": "online",
        "engine": "LeadRadar Pro",
        "pricing_tier": "$15/mo Pro",
        "message": "The Watcher is active."
    }

# --- BANDWIDTH PROTECTOR ---
async def intercept_route(route):
    """Aborts images/css/media to save 90% bandwidth and boost speed."""
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()

# --- THE WATCHER ENGINE ---
async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        # Launch with Stealth Arguments
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Apply the Bandwidth Guard
        await page.route("**/*", intercept_route)
        
        # Inject Stealth Script to hide 'webdriver' presence
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            # Fast load for data extraction (ignore images/css)
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(2) # Give JS a moment to hydrate text data
            html = await page.content()
            
            # 1. REAL ESTATE SCRAPE (IF ZIP)
            leads = []
            if is_zip:
                cards = await page.query_selector_all("[data-testid='property-card']")
                for card in cards[:10]:
                    addr_el = await card.query_selector("[data-label='pc-address']")
                    pri_el = await card.query_selector("[data-label='pc-price']")
                    if addr_el and pri_el:
                        leads.append({
                            "address": (await addr_el.inner_text()).strip(),
                            "price": (await pri_el.inner_text()).strip(),
                            "sqft": (await (await card.query_selector("[data-label='pc-meta-sqft']")).inner_text() if await card.query_selector("[data-label='pc-meta-sqft']") else "N/A"),
                            "days_on_market": (await (await card.query_selector("[data-label='pc-meta-dom']")).inner_text() if await card.query_selector("[data-label='pc-meta-dom']") else "New")
                        })

            # 2. BUSINESS SIGNALS
            tech_found = []
            if "shopify" in html.lower(): tech_found.append({"name": "Shopify", "category": "E-commerce"})
            if "facebook.net" in html.lower(): tech_found.append({"name": "Meta Pixel", "category": "Advertising"})
            if "google-analytics" in html.lower(): tech_found.append({"name": "Google Analytics", "category": "Analytics"})
            
            hiring = any(word in html.lower() for word in ["careers", "hiring", "job-openings", "work-with-us"])
            
            # 3. CONTACTS & SOCIALS
            emails = list(set(EMAIL_PATTERN.findall(html)))[:3]
            socials = {k: v.search(html).group(0) for k, v in SOCIAL_PATTERNS.items() if v.search(html)}

            # 4. LEAD SCORING ENGINE
            score = (len(tech_found) * 15) + (35 if hiring else 0) + (len(socials) * 5) + (15 if emails else 0)
            
            await browser.close()
            return {
                "url": url,
                "lead_score": min(score, 100),
                "hiring_signal": hiring,
                "tech_stack": tech_found,
                "social_profiles": socials,
                "contacts": {"emails": emails},
                "real_estate_leads": leads if is_zip else None,
                "status": "success",
                "optimized": True
            }
        except Exception as e:
            await browser.close()
            return {"error": "Observation failed", "details": str(e)}

# --- API ENDPOINTS ---

@app.get("/analyze")
async def analyze_endpoint(url: str, request: Request):
    # RapidAPI Proxy Security Header Verification
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized Access")
    
    # Internal Semaphore: Queues requests to prevent RAM overflow
    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(url, is_zip=False)

@app.get("/leads/{zip_code}")
async def zip_leads_endpoint(zip_code: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized Access")
    
    async with MAX_CONCURRENT_SCANS:
        return await run_lead_radar(zip_code, is_zip=True)

if __name__ == "__main__":
    # Pulls Port from Railway environment or defaults to 8080
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
