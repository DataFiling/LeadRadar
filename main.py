import os
import re
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro - B2B Intelligence")
app.router.redirect_slashes = False

MAX_CONCURRENT_SCANS = asyncio.Semaphore(3)

# --- ADVANCED SIGNAL PATTERNS ---
PATTERNS = {
    "emails": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', re.I),
    "LinkedIn": re.compile(r"linkedin\.com/(company|in)/[a-z0-9\-_]+", re.I),
    "Facebook_Pixel": re.compile(r"fbevents\.js|connect\.facebook\.net", re.I),
    "Google_Ads": re.compile(r"googletagmanager\.com|googleadservices\.com", re.I)
}

@app.get("/")
async def health_check():
    return {"status": "LeadRadar Intelligence Online", "version": "3.0.1"}

async def run_deep_analysis(url: str):
    # Ensure URL has a scheme (Stops 400s caused by bad input)
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    async with async_playwright() as p:
        browser = None
        try:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            # Increased timeout to 60s to survive Railway's 'Slurry' network
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            if response.status >= 400:
                await browser.close()
                return {"error": "Site Unreachable", "details": f"Target returned status {response.status}"}

            await asyncio.sleep(2) 
            html = await page.content()
            
            # --- SIGNAL EXTRACTION ---
            detected_tech = []
            if PATTERNS["Facebook_Pixel"].search(html): detected_tech.append("Facebook Ads")
            if PATTERNS["Google_Ads"].search(html): detected_tech.append("Google Ads")
            if "shopify" in html.lower(): detected_tech.append("Shopify")
            
            growth_signals = [w for w in ["careers", "hiring", "press", "funding"] if w in html.lower()]
            emails = list(set(PATTERNS["emails"].findall(html)))[:3]
            
            await browser.close()
            return {
                "url": url,
                "lead_score": (len(detected_tech) * 20) + (len(growth_signals) * 10),
                "technographics": detected_tech,
                "growth_signals": growth_signals,
                "contacts": {"emails": emails},
                "status": "success"
            }
        except Exception as e:
            if browser: await browser.close()
            # This detail will show up in your 400 response
            return {"error": "Watcher Error", "details": str(e)}

@app.get("/analyze")
@app.get("/analyze/")
async def analyze_endpoint(url: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized"})
    
    async with MAX_CONCURRENT_SCANS:
        res = await run_deep_analysis(url)
        # If the result has an error, we return 400 with the details
        status_code = 200 if "error" not in res else 400
        return JSONResponse(status_code=status_code, content=res)

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
