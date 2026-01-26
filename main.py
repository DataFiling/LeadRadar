import os
import re
import asyncio
import traceback  # Added for detailed error logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro - Production")

# --- CONCURRENCY GUARD ---
# CHANGED: Reduced to 1 to prevent OOM (Out of Memory) crashes on Railway 1GB plan
MAX_SCANS = asyncio.Semaphore(1)

EMAIL_REGEX = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.(?:com|net|org|io|biz|co|uk|ca)', re.I)
AD_PIXELS = {"Facebook Ads": "fbevents.js", "Google Ads": "googletagmanager.com", "LinkedIn Ads": "snap.licdn.com"}

@app.get("/")
async def health_check():
    return {"status": "LeadRadar Online", "mode": "B2B_Total_Intelligence"}

async def run_analysis(url: str):
    if not url.startswith("http"): url = "https://" + url
    async with async_playwright() as p:
        browser = None
        try:
            # CHANGED: Optimized launch arguments for Docker/Railway environment
            browser = await p.chromium.launch(
                headless=True, 
                args=[
                    "--no-sandbox", 
                    "--disable-setuid-sandbox", 
                    "--disable-dev-shm-usage",  # Critical: Prevents shared memory crashes
                    "--disable-gpu"             # Critical: Saves memory
                ]
            )
            context = await browser.new_context(user_agent="Mozilla/5.0 LeadRadar/Production-3.3")
            page = await context.new_page()
            
            # BLOCK ASSETS: Improves speed and stops "logo@2x.png" false positives
            await page.route("**/*.{png,jpg,jpeg,gif,svg,webp,woff,woff2}", lambda route: route.abort())
            
            # Timeout set to 45s
            await page.goto(url, wait_until="domcontentloaded", timeout=45000)
            html = await page.content()
            
            # --- DATA EXTRACTION ---
            emails = list(set([e.lower() for e in EMAIL_REGEX.findall(html) if not any(x in e.lower() for x in ["@1x", "@2x", "@3x"])]))[:5]
            ads = [name for name, snip in AD_PIXELS.items() if snip in html.lower()]
            # Detect stale copyright years
            is_stale = "2026" not in html and "2025" not in html if "©" in html else False
            
            await browser.close()
            return {
                "url": url,
                "contacts": {"emails": emails},
                "marketing": {"ads_detected": ads, "has_budget_signal": len(ads) > 0},
                "audit": {"is_stale_website": is_stale, "missing_h1": await page.locator('h1').count() == 0},
                "status": "success"
            }
        except Exception as e:
            # CHANGED: Log the full error to Railway console before returning 400
            print(f"CRITICAL SCRAPE ERROR: {str(e)}")
            traceback.print_exc()
            
            if browser: await browser.close()
            return {"error": "Observation failed", "details": str(e)}

@app.get("/analyze")
async def analyze_endpoint(url: str, request: Request):
    # Security Check
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized Agent"})
    
    async with MAX_SCANS:
        res = await run_analysis(url)
        # Returns 200 if successful, 400 if "error" key exists
        return JSONResponse(status_code=200 if "error" not in res else 400, content=res)
