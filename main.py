import os
import re
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro - B2B Intelligence")
app.router.redirect_slashes = False

MAX_CONCURRENT_SCANS = asyncio.Semaphore(3) # Increased back to 3 since B2B sites are lighter

# --- ADVANCED SIGNAL PATTERNS ---
PATTERNS = {
    "emails": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I),
    "LinkedIn": re.compile(r"linkedin\.com/(company|in)/[a-z0-9\-_]+", re.I),
    "X_Twitter": re.compile(r"(twitter\.com|x\.com)/[a-z0-9\-_]+", re.I),
    "Facebook_Pixel": re.compile(r"fbevents\.js|connect\.facebook\.net", re.I),
    "Google_Ads": re.compile(r"googletagmanager\.com|googleadservices\.com", re.I),
    "HubSpot": re.compile(r"js\.hs-scripts\.com|js\.hsadspixel\.net", re.I),
    "Intercom": re.compile(r"widget\.intercom\.io", re.I)
}

@app.get("/")
async def health_check():
    return {"status": "LeadRadar Intelligence Online", "version": "3.0.0"}

async def run_deep_analysis(url: str):
    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Navigate to the target site
            response = await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            await asyncio.sleep(2) # Let the 'Slurry' settle
            html = await page.content()
            
            # --- SIGNAL EXTRACTION ---
            detected_tech = []
            if PATTERNS["Facebook_Pixel"].search(html): detected_tech.append("Facebook Ads")
            if PATTERNS["Google_Ads"].search(html): detected_tech.append("Google Ads")
            if PATTERNS["HubSpot"].search(html): detected_tech.append("HubSpot CRM")
            if PATTERNS["Intercom"].search(html): detected_tech.append("Intercom Chat")
            if "shopify" in html.lower(): detected_tech.append("Shopify")
            
            # Identify Hiring & Growth signals
            growth_keywords = ["careers", "hiring", "press release", "news", "investors", "funding"]
            active_signals = [word for word in growth_keywords if word in html.lower()]
            
            # Contact & Social Mining
            socials = {k: PATTERNS[k].search(html).group(0) for k in ["LinkedIn", "X_Twitter"] if PATTERNS[k].search(html)}
            emails = list(set(PATTERNS["emails"].findall(html)))[:5]
            
            # Scoring Logic (Max 100)
            score = (len(detected_tech) * 15) + (len(active_signals) * 10) + (len(socials) * 5)
            
            await browser.close()
            return {
                "url": url,
                "lead_score": min(score, 100),
                "technographics": detected_tech,
                "growth_signals": active_signals,
                "social_profiles": socials,
                "contacts": {"emails": emails},
                "status": "success"
            }
        except Exception as e:
            if browser: await browser.close()
            return {"error": "Observation failed", "details": str(e)}

@app.get("/analyze")
@app.get("/analyze/")
async def analyze_endpoint(url: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized"})
    
    async with MAX_CONCURRENT_SCANS:
        res = await run_deep_analysis(url)
        return JSONResponse(status_code=200 if "error" not in res else 400, content=res)

# --- CATCH-ALL TO GUIDE USERS ---
@app.api_route("/{path_name:path}", methods=["GET"])
async def catch_all(request: Request, path_name: str):
    return {
        "error": "Path Not Found",
        "message": "This API now focuses exclusively on /analyze for high-fidelity B2B data."
    }
