import os
import re
import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from bs4 import BeautifulSoup

app = FastAPI(title="LeadRadar Unified API")

# --- SECURITY CONFIG ---
# Set this variable in the Railway "Variables" tab
PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET", "default_secret_for_local_test")

async def verify_rapidapi(x_rapidapi_proxy_secret: str = Header(None)):
    if x_rapidapi_proxy_secret != PROXY_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized: RapidAPI Secret Mismatch")

# --- SIGNATURE DATABASES ---
TECH_SIGNATURES = {
    "E-commerce": {"Shopify": r"cdn\.shopify\.com", "WooCommerce": r"woocommerce", "Magento": r"magento"},
    "Analytics": {"Google Analytics": r"googletagmanager", "Meta Pixel": r"facebook\.net/en_US/fbevents\.js"},
    "Marketing": {"HubSpot": r"js\.hs-scripts\.com", "Klaviyo": r"static\.klaviyo\.com"}
}

SIGNAL_KEYWORDS = ["hiring", "careers", "open roles", "join our team", "vacancies"]

# --- CORE LOGIC FUNCTIONS ---

async def perform_scan(url: str):
    if not url.startswith("http"):
        url = f"https://{url}"
        
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            # Fetch main page
            response = await client.get(url)
            html_content = response.text
            headers = str(response.headers)
            combined_data = (html_content + headers).lower()

            # 1. Technographics (#8)
            detected_tech = []
            for category, techs in TECH_SIGNATURES.items():
                for name, pattern in techs.items():
                    if re.search(pattern, combined_data, re.IGNORECASE):
                        detected_tech.append({"name": name, "category": category})

            # 2. Hiring Signals (#4)
            # We check the main page text for a 'Careers' link or keywords
            is_hiring = any(word in combined_data for word in SIGNAL_KEYWORDS)

            # 3. StockWatch (#10)
            # Look for "Out of Stock" indicators
            out_of_stock = any(word in combined_data for word in ["out of stock", "sold out", "unavailable"])

            return {
                "url": url,
                "tech_stack": detected_tech,
                "hiring_signal": is_hiring,
                "stockwatch_alert": out_of_stock,
                "status": "success"
            }
        except Exception as e:
            return {"status": "error", "message": str(e)}

# --- API ENDPOINTS ---

@app.get("/")
def health_check():
    return {"status": "LeadRadar Online", "mode": "Unified"}

@app.get("/analyze")
async def analyze_domain(url: str, _ = Depends(verify_rapidapi)):
    """
    The Master Endpoint for RapidAPI. 
    Combines Tech Detection, B2B Signals, and Inventory Monitoring.
    """
    result = await perform_scan(url)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result["message"])
    return result
