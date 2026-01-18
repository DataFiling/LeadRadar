import os
import asyncio
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro")
MAX_CONCURRENT_SCANS = asyncio.Semaphore(2) # Lowered to 2 to save Railway RAM

@app.get("/")
async def health_check():
    return {"status": "online"}

async def run_lead_radar(target: str, is_zip: bool = False):
    async with async_playwright() as p:
        try:
            # We add specific 'stealth' arguments to prevent Realtor.com from blocking the scan
            browser = await p.chromium.launch(
                headless=True, 
                args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
            )
            context = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = await context.new_page()
            
            url = f"https://www.realtor.com/realestateandhomes-search/{target}" if is_zip else target
            
            # Shorter timeout and better wait condition
            response = await page.goto(url, wait_until="commit", timeout=45000)
            
            if response.status == 403:
                await browser.close()
                return {"error": "Access Denied by Realtor.com", "hint": "Realtor is blocking the server IP."}

            await asyncio.sleep(3) # Let the 'Slurry' of data settle
            
            leads = []
            if is_zip:
                cards = await page.query_selector_all("[data-testid='property-card']")
                for card in cards[:10]:
                    addr = await card.query_selector("[data-label='pc-address']")
                    price = await card.query_selector("[data-label='pc-price']")
                    if addr and price:
                        leads.append({
                            "address": (await addr.inner_text()).strip(),
                            "price": (await price.inner_text()).strip()
                        })

            await browser.close()
            return {"url": url, "leads": leads, "status": "success"}
            
        except Exception as e:
            # This prevents the 500 error and gives you the real error instead
            return {"error": "Watcher Crash", "details": str(e)}

@app.get("/leads/{zip_code}")
async def zip_leads_endpoint(zip_code: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized"})

    async with MAX_CONCURRENT_SCANS:
        result = await run_lead_radar(zip_code, is_zip=True)
        # If the result contains an error, return a 400 instead of crashing with a 500
        if "error" in result:
            return JSONResponse(status_code=400, content=result)
        return result
