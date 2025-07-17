from fastapi import FastAPI, Request, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Dict, Any, List, Optional
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Google Sheets setup
USE_GOOGLE_SHEETS = False
client = None
SHEET_NAME = "mcp"
TAB_NAME = "Sheet1"

google_creds_json = os.getenv("GOOGLE_CLIENT_JSON")
if google_creds_json:
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(google_creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        USE_GOOGLE_SHEETS = True
        logger.info("✅ Google Sheets connected successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Google Sheets client: {e}")

def get_filtered_data(filters: dict = {}) -> List[dict]:
    """Get filtered data from Google Sheets"""
    if not USE_GOOGLE_SHEETS or not client:
        return []
    
    try:
        sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
        rows = sheet.get_all_records()
        
        filtered = []
        for row in rows:
            match = True
            for key, value in filters.items():
                if value:
                    # Case-insensitive partial matching
                    if value.lower() not in str(row.get(key, "")).lower():
                        match = False
                        break
            if match:
                filtered.append(row)
        
        return filtered
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return []

@app.post("/")
async def simple_connector(request: Request):
    """Simple connector endpoint that Claude can easily use"""
    try:
        body = await request.json()
        query = body.get("query", body.get("message", body.get("prompt", "")))
        
        logger.info(f"Query received: {query}")
        
        # Parse the query to understand intent
        query_lower = query.lower()
        
        # Check for help or tool listing
        if any(word in query_lower for word in ["help", "tools", "commands", "what can"]):
            return JSONResponse({
                "response": """I can help you with CRM operations:

**Available Commands:**
• Get leads: "show leads", "get all leads", "list leads"
• Filter by platform: "get SHOPIFY leads", "show WOOCOMMERCE leads"
• Filter by billing: "get CONTRACT leads", "show USAGE billing leads"
• Filter by type: "get 1P leads", "show 2P leads"
• Filter by cart recovery: "get enabled cart recovery leads"
• Filter by provider: "get klaviyo leads", "show facebook provider leads"
• Add lead: "add lead [TeamName] [Domain] [Platform]"

**Examples:**
- "Show me all SHOPIFY leads"
- "Get CONTRACT billing leads"
- "List 1P type leads with klaviyo provider"
- "Add lead AcmeCorp acme.com SHOPIFY"
""",
                "status": "ready",
                "google_sheets_connected": USE_GOOGLE_SHEETS
            })
        
        # Handle get/show/list leads requests
        elif any(word in query_lower for word in ["get", "show", "list", "find"]) and "lead" in query_lower:
            filters = {}
            
            # Extract filters from query
            # Platform filters
            for platform in ["SHOPIFY", "WOOCOMMERCE", "EDGETAG", "BIGCOMMERCE", "SALESFORCE"]:
                if platform.lower() in query_lower:
                    filters["Platform"] = platform
            
            # Billing type filters
            for billing in ["USAGE", "CONTRACT", "FREE"]:
                if billing.lower() in query_lower:
                    filters["BillingType"] = billing
            
            # Type filters
            if "1p" in query_lower:
                filters["Type"] = "1P"
            elif "2p" in query_lower:
                filters["Type"] = "2P"
            
            # Cart recovery filters
            for mode in ["enabled", "disabled", "preview", "ab-test"]:
                if mode in query_lower and "cart" in query_lower:
                    filters["CartRecoveryMode"] = mode
            
            # Provider filters
            providers = ["klaviyo", "facebook", "shopify", "tiktok", "pinterest", "googleAnalytics4"]
            for provider in providers:
                if provider.lower() in query_lower:
                    filters["Providers"] = provider
            
            # Get data
            leads = get_filtered_data(filters)
            
            # Limit results
            limit = 10
            if "all" in query_lower:
                limit = 100
            elif any(f"{n} lead" in query_lower for n in ["5", "20", "25", "50"]):
                for n in [5, 20, 25, 50]:
                    if str(n) in query_lower:
                        limit = n
                        break
            
            leads = leads[:limit]
            
            if not leads:
                if not USE_GOOGLE_SHEETS:
                    return JSONResponse({
                        "response": "❌ Google Sheets is not connected. Please set up GOOGLE_CLIENT_JSON environment variable in Railway.",
                        "error": "no_connection"
                    })
                else:
                    return JSONResponse({
                        "response": "No leads found matching your criteria.",
                        "filters_used": filters
                    })
            
            # Format response
            response_text = f"Found {len(leads)} leads"
            if filters:
                response_text += f" (filtered by: {', '.join([f'{k}={v}' for k,v in filters.items()])})"
            response_text += ":\n\n"
            
            for i, lead in enumerate(leads, 1):
                response_text += f"**{i}. {lead.get('TeamName', 'N/A')}**\n"
                response_text += f"   • Domain: {lead.get('Domain', 'N/A')}\n"
                response_text += f"   • Platform: {lead.get('Platform', 'N/A')}\n"
                response_text += f"   • Billing: {lead.get('BillingType', 'N/A')}\n"
                response_text += f"   • Type: {lead.get('Type', 'N/A')}\n"
                response_text += f"   • Cart Recovery: {lead.get('CartRecoveryMode', 'N/A')}\n"
                response_text += f"   • Revenue: ${lead.get('Revenue', '0')}\n"
                if i < len(leads):
                    response_text += "\n"
            
            return JSONResponse({
                "response": response_text,
                "count": len(leads),
                "filters": filters
            })
        
        # Handle add lead requests
        elif "add lead" in query_lower:
            if not USE_GOOGLE_SHEETS:
                return JSONResponse({
                    "response": "❌ Cannot add lead: Google Sheets not connected.",
                    "error": "no_connection"
                })
            
            # Parse add lead command
            parts = query.split()
            if len(parts) >= 5:  # "add lead TeamName Domain Platform"
                try:
                    idx = parts.index("lead") + 1
                    team_name = parts[idx] if idx < len(parts) else "Unknown"
                    domain = parts[idx + 1] if idx + 1 < len(parts) else "unknown.com"
                    platform = parts[idx + 2].upper() if idx + 2 < len(parts) else "SHOPIFY"
                    
                    # Add to sheet
                    sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
                    new_row = [
                        "",  # TagId
                        team_name,
                        domain,
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "", "", # Versions, LastDeployment
                        platform,
                        "Active",
                        "", "", "", # OperationType, Providers, Plugins
                        "CONTRACT",
                        "1P",
                        "",  # Contacts
                        "N/A",  # CartRecoveryMode
                        "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0",  # All numeric fields
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ]
                    sheet.append_row(new_row)
                    
                    return JSONResponse({
                        "response": f"✅ Lead added successfully!\n\nTeam: {team_name}\nDomain: {domain}\nPlatform: {platform}",
                        "success": True
                    })
                except Exception as e:
                    return JSONResponse({
                        "response": f"❌ Failed to add lead: {str(e)}",
                        "error": str(e)
                    })
            else:
                return JSONResponse({
                    "response": "To add a lead, use: add lead [TeamName] [Domain] [Platform]\nExample: add lead AcmeCorp acme.com SHOPIFY",
                    "error": "invalid_format"
                })
        
        # Default response
        else:
            return JSONResponse({
                "response": "I can help you manage CRM leads. Try:\n• 'Show all leads'\n• 'Get SHOPIFY leads'\n• 'List CONTRACT billing leads'\n• 'Help' for all commands",
                "hint": "Use natural language to interact with the CRM"
            })
            
    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse({
            "response": f"Error: {str(e)}",
            "error": str(e)
        }, status_code=500)

@app.get("/")
async def root():
    return {
        "message": "Simple CRM API Server",
        "status": "ready",
        "google_sheets_connected": USE_GOOGLE_SHEETS,
        "instructions": "Send POST requests with {\"query\": \"your command\"}"
    }

@app.get("/status")
async def status():
    if USE_GOOGLE_SHEETS:
        try:
            sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
            count = len(sheet.get_all_records())
            return {
                "connected": True,
                "sheet": SHEET_NAME,
                "records": count
            }
        except:
            return {"connected": False, "error": "Failed to access sheet"}
    else:
        return {"connected": False, "message": "Google Sheets not configured"}

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting Simple CRM API Server on port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
