import os
import re
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI()

# --- 1. HEARTBEAT ---
@app.get("/")
async def health_check():
    return {"status": "LeadRadar Online", "mode": "B2B_Deep_Analysis"}

# --- 2. THE ENGINE ---
async def run_analysis(url: str):
    # Ensure URL is properly formatted
    if not url.startswith("http"):
        url = "https://" + url

    async with async_playwright() as p:
        browser = None
        try:
            # Launch with specific arguments for Docker environments
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            context = await browser.new_context(user_agent="Mozilla/5.0")
            page = await context.new_page()
            
            # Navigate with a 60-second timeout
            response = await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            html = await page.content()
            
            # Simple Signal Extraction
            tech = []
            if "shopify" in html.lower(): tech.append("Shopify")
            if "googletagmanager" in html.lower(): tech.append("Google Ads")
            
            await browser.close()
            return {
                "url": url,
                "status": "success",
                "technographics": tech,
                "hiring": "hiring" in html.lower()
            }
        except Exception as e:
            if browser: await browser.close()
            # This prints the REAL error to your Railway Logs
            print(f"CRITICAL WATCHER ERROR: {str(e)}")
            return {"error": "Watcher Failed", "details": str(e)}

# --- 3. THE ENDPOINT ---
@app.get("/analyze")
async def analyze(url: str, request: Request):
    # Security Check
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized"})

    # Run the Watcher
    res = await run_analysis(url)
    
    if "error" in res:
        return JSONResponse(status_code=400, content=res)
    return res
