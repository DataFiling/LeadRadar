import os
import re
import asyncio
import time
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from playwright.async_api import async_playwright

app = FastAPI(title="LeadRadar Pro - Premium Intelligence")

# --- EXPANDED TECH & SIGNAL PATTERNS ---
TECH_MAP = {
    "E-commerce": {"Shopify": "shopify.com", "WooCommerce": "wp-content/plugins/woocommerce"},
    "Marketing": {"HubSpot": "hs-scripts.com", "Mailchimp": "chimpstatic.com", "Klaviyo": "klaviyo.com"},
    "Analytics": {"Google Analytics": "googletagmanager.com", "Facebook Pixel": "fbevents.js", "Hotjar": "static.hotjar.com"},
    "Frameworks": {"React": "_next/static", "Vue": "vue.js", "Elementor": "elementor"}
}

@app.get("/")
async def health_check():
    return {"status": "LeadRadar Premium Online", "version": "3.1.0"}

async def run_premium_analysis(url: str):
    if not url.startswith("http"): url = "https://" + url

    async with async_playwright() as p:
        browser = None
        try:
            start_time = time.time()
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
            context = await browser.new_context(user_agent="Mozilla/5.0 LeadRadar/3.0")
            page = await context.new_page()
            
            # Navigate and measure load speed
            response = await page.goto(url, wait_until="networkidle", timeout=60000)
            load_speed = round(time.time() - start_time, 2)
            
            html = await page.content()
            
            # --- 1. SEO AUDIT LOGIC ---
            seo = {
                "title": await page.title(),
                "has_meta_description": await page.locator('meta[name="description"]').count() > 0,
                "has_h1": await page.locator('h1').count() > 0,
                "missing_img_alts": await page.eval_on_selector_all('img:not([alt])', 'imgs => imgs.length'),
                "is_secure": url.startswith("https")
            }
            
            # --- 2. ENHANCED TECHNOGRAPHICS ---
            detected_tech = []
            for category, providers in TECH_MAP.items():
                for name, snippet in providers.items():
                    if snippet in html.lower():
                        detected_tech.append({"name": name, "category": category})
            
            # --- 3. GROWTH & CONTACTS ---
            emails = list(set(re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', html)))[:3]
            hiring = any(w in html.lower() for w in ["careers", "hiring", "openings"])

            await browser.close()
            return {
                "url": url,
                "performance": {"load_speed_seconds": load_speed},
                "seo_audit": seo,
                "technographics": detected_tech,
                "signals": {"hiring": hiring, "emails": emails},
                "lead_score": (len(detected_tech) * 10) + (30 if seo["has_meta_description"] is False else 0)
            }
        except Exception as e:
            if browser: await browser.close()
            return {"error": "Observation failed", "details": str(e)}

@app.get("/analyze")
async def analyze_endpoint(url: str, request: Request):
    if request.headers.get("X-RapidAPI-Proxy-Secret") != os.getenv("RAPIDAPI_PROXY_SECRET"):
        return JSONResponse(status_code=403, content={"detail": "Unauthorized"})
    
    res = await run_premium_analysis(url)
    return JSONResponse(status_code=200 if "error" not in res else 400, content=res)
