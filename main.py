async def run_scrape_logic(zip_code: str):
    async with async_playwright() as p:
        # Launch with Stealth Args
        browser = await p.chromium.launch(
            headless=True, 
            args=["--no-sandbox", "--disable-setuid-sandbox", "--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        url = f"https://www.realtor.com/realestateandhomes-search/{zip_code}"
        
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(3) 
            await page.wait_for_selector("[data-testid='property-card']", timeout=20000)
            
            listings = await page.query_selector_all("[data-testid='property-card']")
            leads = []
            
            for listing in listings[:10]:
                # Core Elements
                address_el = await listing.query_selector("[data-label='pc-address']")
                price_el = await listing.query_selector("[data-label='pc-price']")
                
                # NEW: Metadata Elements (Sqft and Days on Market)
                # These often appear in a list; we'll grab the specific labels
                sqft_el = await listing.query_selector("[data-label='pc-meta-sqft']")
                dom_el = await listing.query_selector("[data-label='pc-meta-dom']") # Note: Selector may vary based on region
                
                if address_el and price_el:
                    addr = await address_el.inner_text()
                    pri = await price_el.inner_text()
                    
                    # Extraction with Fallbacks
                    sqft = await sqft_el.inner_text() if sqft_el else "N/A"
                    dom = await dom_el.inner_text() if dom_el else "New"

                    leads.append({
                        "address": addr.strip().replace('\n', ' '),
                        "price": pri.strip(),
                        "sqft": sqft.strip(),
                        "days_on_market": dom.strip()
                    })
            
            await browser.close()
            return leads

        except Exception as e:
            await browser.close()
            return {"error": "Scrape failed", "details": str(e)}
