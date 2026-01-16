import os
import re
import httpx
from fastapi import FastAPI, HTTPException, Header, Depends
from typing import Dict, List, Optional

app = FastAPI(title="LeadRadar Unified API - 2026 Production")

# --- SECURITY CONFIG ---
# Set this in your Railway Variables as RAPIDAPI_PROXY_SECRET
# It must match the secret found in your RapidAPI Provider Dashboard
PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET", "default_secret_for_local_test")

async def verify_rapidapi(
    # We use an alias to ensure FastAPI looks for the exact header RapidAPI sends
    x_rapidapi_proxy_secret: Optional[str] = Header(None, alias="X-RapidAPI-Proxy-Secret")
):
    if not x_rapidapi_proxy_secret or x_rapidapi_proxy_secret != PROXY_SECRET:
        raise HTTPException(
            status_code=403, 
            detail="Unauthorized: Secret Mismatch. Verify Railway Env Variables."
        )

# --- SIGNATURE DATABASES (Pre-compiled for efficiency) ---
TECH_SIGNATURES = {
    "AI_LLM": {
        "OpenAI": re.compile(r"openai\.com", re.I),
        "Anthropic": re.compile(r"anthropic\.com", re.I),
        "LangChain": re.compile(r"langchain", re.I),
        "Pinecone": re.compile(r"pinecone\.io", re.I),
        "Vercel AI": re.compile(r"sdk\.vercel\.ai", re.I)
    },
    "E-commerce": {
        "Shopify": re.compile(r"cdn\.shopify\.com", re.I),
        "WooCommerce": re.compile(r"woocommerce", re.I),
        "BigCommerce": re.compile(r"mybigcommerce\.com", re.I)
    },
    "Analytics": {
        "Google Analytics": re.compile(r"googletagmanager", re.I),
        "Meta Pixel": re.compile(r"facebook\.net", re.I),
        "Hotjar": re.compile(r"static\.hotjar\.com", re.I)
    }
}

HIRING_KEYWORDS = ["hiring", "careers", "open roles", "join our team", "vacancies"]
STOCK_KEYWORDS = ["out of stock", "sold out", "unavailable", "backorder"]

# --- CORE LOGIC ---

async def perform_scan(url: str) -> Dict:
    if not url.startswith("http"):
        url = f"https://{url}"
        
    # Professional User-Agent to avoid basic bot blocks
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) LeadRadarBot/1.1 (Scraper; Railway Hosted)"
    }

    async with httpx.AsyncClient(timeout=15.0, follow_redirects=True, headers=headers) as client:
        try:
            response = await client.get(url)
            response.raise_for_status() # Trigger error for 4xx/5xx responses
            
            html = response.text
            lower_content = html.lower()
            resp_headers = str(response.headers).lower()
            combined_search_area = html + resp_headers

            # 1. Technographics Scan
            tech_found = []
            for cat, techs in TECH_SIGNATURES.items():
                for name, pattern in techs.items():
                    if pattern.search(combined_search_area):
                        tech_found.append({"name": name, "category": cat})

            # 2. Signals
            hiring = any(word in lower_content for word in HIRING_KEYWORDS)
            stockout = any(word in lower_content for word in STOCK_KEYWORDS)

            return {
                "url": url,
                "tech_stack": tech_found,
                "hiring_signal": hiring,
                "stockwatch_alert": stockout,
                "status": "success"
            }
        except httpx.HTTPStatusError as e:
            return {"status": "error", "message": f"Site blocked or unavailable: {e.response.status_code}"}
        except Exception as e:
            return {"status": "error", "message": str(e)}

# --- ENDPOINTS ---

@app.get("/")
def health_check():
    """Confirms the service is live and reachable by Railway/RapidAPI."""
    return {"status": "LeadRadar Online", "version": "2026.1"}

@app.get("/analyze")
async def analyze(url: str, _ = Depends(verify_rapidapi)):
    """The main scraper endpoint. Protected by RapidAPI Proxy Secret."""
    result = await perform_scan(url)
    if result.get("status") == "error":
        return result # Return the error detail in JSON format
    return result

if __name__ == "__main__":
    import uvicorn
    # Local testing fallback
    port = int(os.getenv("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
