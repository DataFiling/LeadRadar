from fastapi import FastAPI, HTTPException, Header, Depends
import httpx
import re
import os
from bs4 import BeautifulSoup

app = FastAPI(title="LeadRadar API")

# Setup Security
PROXY_SECRET = os.getenv("RAPIDAPI_PROXY_SECRET")

# Signature Data
TECH_SIGNATURES = {
    "E-commerce": {"Shopify": r"cdn\.shopify\.com", "WooCommerce": r"woocommerce"},
    "Marketing": {"HubSpot": r"js.hs-scripts.com", "Klaviyo": r"static.klaviyo.com"},
    "Frameworks": {"React": r"data-reactroot", "WordPress": r"wp-content"}
}

# Hiring Signals
SIGNAL_KEYWORDS = {
    "Expansion": ["hiring", "open roles", "careers"],
    "Sales_Growth": ["account executive", "sales manager", "outreach"],
    "Tech_Investment": ["software engineer", "devops", "cloud architect"]
}

async def verify_request(x_rapidapi_proxy_secret: str = Header(None)):
    if x_rapidapi_proxy_secret != PROXY_SECRET:
        raise HTTPException(status_code=403, detail="Unauthorized")

@app.get("/enrich")
async def enrich_company(url: str, _ = Depends(verify_request)):
    clean_url = url if url.startswith("http") else f"https://{url}"
    domain = clean_url.replace("https://", "").replace("http://", "").split('/')[0]
    
    async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
        try:
            # 1. Tech Detection
            res = await client.get(clean_url)
            tech_found = [name for cat, techs in TECH_SIGNATURES.items() 
                          for name, pat in techs.items() if re.search(pat, res.text)]
            
            # 2. Hiring Signal Detection
            signals = []
            career_res = await client.get(f"{clean_url}/careers")
            if career_res.status_code == 200:
                text = career_res.text.lower()
                signals = [cat for cat, words in SIGNAL_KEYWORDS.items() 
                           if any(w in text for w in words)]

            return {
                "domain": domain,
                "tech_stack": tech_found,
                "buying_signals": signals,
                "intent_score": len(tech_found) + (len(signals) * 2)
            }
        except Exception as e:
            return {"error": "Could not scan domain", "details": str(e)}
