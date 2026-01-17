import os
import re
import asyncio
from fastapi import FastAPI, Request, HTTPException
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro")

# --- BANDWIDTH PROTECTOR ---
async def intercept_route(route):
    """
    Aborts requests for unnecessary assets. 
    This cuts data usage by up to 90% and speeds up the 'Watcher'.
    """
    # We block images, media (video/audio), fonts, and styles.
    # We keep 'script' and 'document' because we need them for data extraction.
    if route.request.resource_type in ["image", "media", "font", "stylesheet"]:
        await route.abort()
    else:
        await route.continue_()

async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # 1. ATTACH THE BANDWIDTH PROTECTOR
        # This is the "Kenotic Shift" - emptying the noise to find the signal.
        await page.route("**/*", intercept_route)

        url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target

        try:
            # We use 'domcontentloaded' because we don't need to wait for heavy assets anymore
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            
            # Allow 2 seconds for vital JS-driven data to hydrate
            await asyncio.sleep(2) 
            
            html = await page.content()
            
            # --- EXTRACTION LOGIC ---
            # (Hiring signals, Tech Stack, Emails, and Scoring logic here)
            
            # Example Score (Logic from previous steps applies here)
            final_score = 85 

            await browser.close()
            return {
                "url": url,
                "lead_score": final_score,
                "status": "success",
                "bandwidth_optimized": True
            }
            
        except Exception as e:
            await browser.close()
            return {"error": str(e)}

# --- ENDPOINT ---
@app.get("/analyze")
async def analyze(url: str, request: Request):
    # Verify Proxy Secret from Railway Env
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        raise HTTPException(status_code=403, detail="Unauthorized")
    return await run_lead_radar(url)
