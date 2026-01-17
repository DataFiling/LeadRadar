import os
import re
import asyncio
import subprocess
import uvicorn
from fastapi import FastAPI, Request, HTTPException, Depends
from playwright.async_api import async_playwright

# --- INITIALIZATION ---
try:
    subprocess.run(["playwright", "install", "--with-deps", "chromium"], check=True)
except Exception as e:
    print(f"Browser check: {e}")

app = FastAPI(title="LeadRadar API")

# --- PATTERNS & SIGNATURES ---
SOCIAL_PATTERNS = {
    "LinkedIn": re.compile(r"linkedin\.com/(company|in)/[a-z0-9\-_]+", re.I),
    "X_Twitter": re.compile(r"(twitter\.com|x\.com)/[a-z0-9\-_]+", re.I),
    "Instagram": re.compile(r"instagram\.com/[a-z0-9\-_]+", re.I)
}
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I)
TECH_SIGNATURES = {
    "E-commerce": {"Shopify": "shopify", "WooCommerce": "woocommerce", "Magento": "magento"},
    "Analytics": {"Google Analytics": "google-analytics", "Hotjar": "hotjar"},
    "Advertising": {"Meta Pixel": "facebook.net", "TikTok Pixel": "tiktok.com/analytics"}
}

# --- CORE LOGIC: THE WATCHER ---
async def perform_advanced_scrape(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        # Stealth Injection
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=60000)
            html = await page.content()
            
            # 1. REAL ESTATE LOGIC
            leads = []
            if is_zip:
                await page.wait_for_selector("[data-testid='property-card']", timeout=10000)
                cards = await page.query_selector_all("[data-testid='property-card']")
                for card in cards[:10]:
                    addr = await (await card.query_selector("[data-label='pc-address']")).inner_text()
                    pri = await (await card.query_selector("[data-label='pc-price']")).inner_text()
                    sqft = await (await card.query_selector("[data-label='pc-meta-sqft']")).inner_text() if await card.query_selector("[data-label='pc-meta-sqft']") else "N/A"
                    dom = await (await card.query_selector("[data-label='pc-meta-dom']")).inner_text() if await card.query_selector("[data-label='pc-meta-dom']") else "New"
                    leads.append({"address": addr.strip(), "price": pri.strip(), "sqft": sqft, "days_on_market": dom})

            # 2. BUSINESS/TECH LOGIC
            tech_found = [name for cat, techs in TECH_SIGNATURES.items() for name, sig in techs.items() if sig in html.lower()]
            hiring = any(word in html.lower() for word in ["careers", "hiring", "job-openings"])
            
            # 3. IDENTITY RESOLUTION
            socials = {k: v.search(html).group(0) for k, v in SOCIAL_PATTERNS.items() if v.search(html)}
            emails = list(set(EMAIL_PATTERN.findall(html)))[:3]

            # 4. LEAD SCORING ENGINE
            score = (len(tech_found) * 15) + (35 if hiring else 0) + (len(socials) * 5) + (15 if emails else 0)
            final_score = min(score, 100)

            await browser.close()
            return {
                "url": url,
                "lead_score": final_score,
                "hiring_signal": hiring,
                "tech_stack": tech_found,
                "social_profiles": socials,
                "contacts": {"emails": emails},
                "real_estate_leads": leads if is_zip else "N/A",
                "status": "success"
            }
        except Exception as e:
            await browser.close()
            return {"error": "Scrape failed", "details": str(e)}

# --- API ROUTES ---

@app.get("/analyze")
async def analyze_company(url: str, request: Request):
    # Verify Proxy Secret from Railway Env
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    return await perform_advanced_scrape(url, is_zip=False)

@app.get("/leads/{zip_code}")
async def get_real_estate(zip_code: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    return await perform_advanced_scrape(zip_code, is_zip=True)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
