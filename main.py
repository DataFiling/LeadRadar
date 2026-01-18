import os
import re
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro - Total Intelligence")

# --- PATTERN RECOGNITION ---
# Refined to ignore image artifacts like @2x
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:com|net|org|io|biz|co)', re.I)
AD_PIXELS = {
    "Facebook Ads": "fbevents.js",
    "Google Ads": "googletagmanager.com",
    "LinkedIn Ads": "snap.licdn.com"
}

@app.get("/")
async def health_check():
    return {"status": "LeadRadar Online", "mode": "B2B_Total_Intelligence"}

async def run_analysis(url: str):
    if not url.startswith("http"): url = "https://" + url

    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent="Mozilla/5.0 LeadRadar/3.3")
            page = await context.new_page()
            
            # BLOCK IMAGES: Prevents logo@2x.png from being misread as an email
            await page.route("**/*.{png,jpg,jpeg,gif,svg,webp}", lambda route: route.abort())
            
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            html = await page.content()
            
            # --- 1. CONTACT EXTRACTION ---
            emails = list(set([e.lower() for e in EMAIL_REGEX.findall(html) if "@" in e and not any(x in e for x in ["@1x", "@2x", "@3x"])]))[:5]

            # --- 2. ADVERTISING & TECH SIGNALS ---
            ads_detected = [name for name, snippet in AD_PIXELS.items() if snippet in html.lower()]
            
            # --- 3. SEO & PAIN POINT AUDIT ---
            is_stale = "2026" not in html and "2025" not in html if "©" in html else False
            missing_h1 = await page.locator('h1').count() == 0
            has_lead_magnet = any(x in html.lower() for x in ["subscribe", "newsletter", "download", "get a quote"])

            await browser.close()
            return {
                "url": url,
                "contacts": {"emails": emails},
                "marketing": {
                    "ads_detected": ads_detected,
                    "has_budget_signal": len(ads_detected) > 0,
                    "lead_capture_found": has_lead_magnet
                },
                "technical_audit": {
                    "is_stale_website": is_stale,
                    "missing_h1_seo_tag": missing_h1,
                    "security": "HTTPS" if url.startswith("https") else "INSECURE"
                },
                "status": "success"
            }
        except Exception as e:
            if browser: await browser.close()
            return {"error": "Observation failed", "details": str(e)}

@app.get("/analyze")
async def analyze_endpoint(url: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized Agent"})
    
    res = await run_analysis(url)
    return JSONResponse(status_code=200 if "error" not in res else 400, content=res)
