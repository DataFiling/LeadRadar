import os
import re
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro - High Fidelity")

# --- THE SELECTIVE WATCHER PATTERNS ---
# This Regex now ignores common image artifacts and looks for standard TLDs
EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:com|net|org|io|gov|edu|biz)', re.I)

@app.get("/")
async def health_check():
    return {"status": "LeadRadar Intelligence Online", "mode": "B2B_High_Fidelity"}

async def run_analysis(url: str):
    if not url.startswith("http"): url = "https://" + url

    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent="Mozilla/5.0 LeadRadar/3.2")
            page = await context.new_page()
            
            # Speeding up the scan by ignoring images and fonts entirely
            await page.route("**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2,ttf}", lambda route: route.abort())
            
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            html = await page.content()
            
            # --- 1. FILTERED CONTACT EXTRACTION ---
            found = EMAIL_REGEX.findall(html)
            # Kill anything that looks like a Retina asset (logo@2x, etc.)
            clean_emails = [e.lower() for e in found if not any(x in e.lower() for x in ['@1x', '@2x', '@3x'])]
            emails = list(set(clean_emails))[:5]

            # --- 2. THE NEW "STALE" SIGNAL (The Leads Replacement) ---
            # Instead of Real Estate, we find "Stale" Websites.
            # If the copyright is 2023 or older, it's a hot lead for a redesign.
            is_stale = False
            if "©" in html or "Copyright" in html:
                if not any(yr in html for yr in ["2024", "2025", "2026"]):
                    is_stale = True

            await browser.close()
            return {
                "url": url,
                "contacts": {"emails": emails},
                "growth_signals": {
                    "stale_website_alert": is_stale,
                    "hiring": "hiring" in html.lower() or "careers" in html.lower()
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
