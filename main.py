import os
import re
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro - B2B Intelligence")

# --- EXPANDED SIGNALS ---
SIGNS = {
    "Shopify": "shopify.com",
    "WordPress": "wp-content",
    "Google Analytics": "googletagmanager.com",
    "Facebook Ads": "fbevents.js",
    "HubSpot": "hs-scripts.com",
    "Intercom": "widget.intercom.io",
    "React": "_next/static"
}

@app.get("/")
async def health_check():
    return {"status": "LeadRadar Intelligence Online", "version": "3.0.2"}

async def run_deep_analysis(url: str):
    if not url.startswith("http"):
        url = "https://" + url

    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
            page = await context.new_page()
            
            # Navigate and wait for the page to be 'settled'
            await page.goto(url, wait_until="networkidle", timeout=60000)
            html = await page.content()
            
            # 1. Technographics Detection
            found_tech = [name for name, snippet in SIGNS.items() if snippet in html.lower()]
            
            # 2. Hiring Signal
            hiring_keywords = ["careers", "hiring", "openings", "jobs", "join our team"]
            is_hiring = any(word in html.lower() for word in hiring_keywords)
            
            # 3. Email Extraction (The 'Contact' Signal)
            emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))[:3]

            await browser.close()
            return {
                "url": url,
                "status": "success",
                "technographics": found_tech,
                "hiring_signal": is_hiring,
                "contacts": {"emails": emails},
                "lead_score": (len(found_tech) * 15) + (25 if is_hiring else 0)
            }
        except Exception as e:
            if browser: await browser.close()
            return {"error": "Watcher Error", "details": str(e)}

@app.get("/analyze")
async def analyze_endpoint(url: str, request: Request):
    # Security Secret Check
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized"})
    
    res = await run_deep_analysis(url)
    return JSONResponse(status_code=200 if "error" not in res else 400, content=res)
