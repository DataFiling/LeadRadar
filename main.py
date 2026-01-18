import os
import re
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro")
app.router.redirect_slashes = False

# --- CONFIGURATION ---
MAX_CONCURRENT_SCANS = asyncio.Semaphore(2)
EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I)
SOCIAL_PATTERNS = {
    "LinkedIn": re.compile(r"linkedin\.com/(company|in)/[a-z0-9\-_]+", re.I),
    "X_Twitter": re.compile(r"(twitter\.com|x\.com)/[a-z0-9\-_]+", re.I),
    "Instagram": re.compile(r"instagram\.com/[a-z0-9\-_]+", re.I)
}

# --- 1. HEARTBEAT ---
@app.get("/")
async def health_check():
    return {"status": "LeadRadar Online", "version": "2.0.2"}

# --- 2. THE WATCHER ENGINE (Unified) ---
async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        try:
            # Stealth launch to bypass Realtor.com and Business firewalls
            browser = await p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
            
            # Navigate with a generous timeout for Railway's network
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            if response.status == 403:
                await browser.close()
                return {"error": "Access Denied", "details": "The target site blocked the Watcher IP."}

            await asyncio.sleep(2) 
            html = await page.content()
            
            # --- DATA EXTRACTION ---
            results = {"url": url, "status": "success"}

            if is_zip:
                # Real Estate Arbitrage Logic
                leads = []
                cards = await page.query_selector_all("[data-testid='property-card']")
                for card in cards[:10]:
                    addr = await card.query_selector("[data-label='pc-address']")
                    price = await card.query_selector("[data-label='pc-price']")
                    if addr and price:
                        leads.append({"address": (await addr.inner_text()).strip(), "price": (await price.inner_text()).strip()})
                results["real_estate_leads"] = leads
            else:
                # Technographics & B2B Signal Logic
                tech = []
                if "shopify" in html.lower(): tech.append({"name": "Shopify", "category": "E-commerce"})
                if "wordpress" in html.lower(): tech.append({"name": "WordPress", "category": "CMS"})
                
                hiring = any(word in html.lower() for word in ["careers", "hiring", "job-openings"])
                emails = list(set(EMAIL_PATTERN.findall(html)))[:3]
                socials = {k: v.search(html).group(0) for k, v in SOCIAL_PATTERNS.items() if v.search(html)}
                
                results.update({
                    "tech_stack": tech,
                    "hiring_signal": hiring,
                    "social_profiles": socials,
                    "contacts": {"emails": emails},
                    "lead_score": (len(tech) * 20) + (30 if hiring else 0) + (len(socials) * 10)
                })

            await browser.close()
            return results

        except Exception as e:
            if 'browser' in locals(): await browser.close()
            return {"error": "Watcher Crash", "details": str(e)}

# --- 3. ENDPOINTS ---

@app.get("/analyze")
@app.get("/analyze/")
async def analyze_endpoint(url: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized"})
    async with MAX_CONCURRENT_SCANS:
        res = await run_lead_radar(url, is_zip=False)
        return JSONResponse(status_code=200 if "error" not in res else 400, content=res)

@app.get("/leads/{zip_code}")
@app.get("/leads/{zip_code}/")
async def zip_leads_endpoint(zip_code: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized"})
    async with MAX_CONCURRENT_SCANS:
        res = await run_lead_radar(zip_code, is_zip=True)
        return JSONResponse(status_code=200 if "error" not in res else 400, content=res)

# --- 4. CATCH-ALL DEBUG ---
@app.api_route("/{path_name:path}", methods=["GET"])
async def catch_all(request: Request, path_name: str):
    return {"error": "Path Not Found", "received_path": f"/{path_name}"}
