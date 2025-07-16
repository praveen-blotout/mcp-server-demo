from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import csv
import io

app = FastAPI()

# ✅ Add CORS middleware for Claude
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with Claude's domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Google Sheets Setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_creds_json = os.getenv("GOOGLE_CLIENT_JSON")

if not google_creds_json:
    raise RuntimeError("GOOGLE_CLIENT_JSON environment variable is not set.")

try:
    creds_dict = json.loads(google_creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
except Exception as e:
    raise RuntimeError(f"Failed to initialize Google Sheets client: {e}")

SHEET_NAME = "mcp"
TAB_NAME = "Sheet1"

# ✅ Data Filter Utility
def get_filtered_data(sheet_name: str, tab_name: str, filters: dict = {}) -> List[dict]:
    try:
        sheet = client.open(sheet_name).worksheet(tab_name)
        rows = sheet.get_all_records()

        filtered = []
        for row in rows:
            match = True
            for key, value in filters.items():
                if value and value.lower() not in str(row.get(key, "")).lower():
                    match = False
                    break
            if match:
                filtered.append(row)
        return filtered
    except Exception as e:
        raise RuntimeError(f"Failed to fetch data: {e}")

# ✅ Models
class Lead(BaseModel):
    name: str
    email: str
    phone: str

# ✅ COMPLETELY PUBLIC ENDPOINTS (NO AUTH)
@app.get("/")
def read_root():
    return {"message": "✅ Google Sheets MCP Server is running 🚀", "status": "healthy"}

@app.get("/crm/leads")
def get_leads_public(
    domain: Optional[str] = None,
    platform: Optional[str] = None,
    billingtype: Optional[str] = None,
    type: Optional[str] = None,
    cartrecoverymode: Optional[str] = None,
    api_key: Optional[str] = None  # Optional API key for internal use
):
    # Optional API key validation (but don't require it)
    secret = os.getenv("API_SECRET_KEY")
    if api_key and secret and api_key != secret:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    try:
        filters = {
            "Domain": domain,
            "Platform": platform,
            "BillingType": billingtype,
            "Type": type,
            "CartRecoveryMode": cartrecoverymode,
        }
        data = get_filtered_data(SHEET_NAME, TAB_NAME, filters)
        return JSONResponse(content=data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch leads: {e}")

@app.post("/crm/leads")
def add_lead_public(lead: Lead, api_key: Optional[str] = None):
    # Optional API key validation
    secret = os.getenv("API_SECRET_KEY")
    if api_key and secret and api_key != secret:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    try:
        sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
        sheet.append_row([lead.name, lead.email, lead.phone])
        return {"message": "Lead added successfully ✅"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add lead: {e}")

@app.get("/crm/leads/export")
def export_leads_public(
    domain: Optional[str] = None,
    platform: Optional[str] = None,
    billingtype: Optional[str] = None,
    type: Optional[str] = None,
    cartrecoverymode: Optional[str] = None,
    api_key: Optional[str] = None
):
    # Optional API key validation
    secret = os.getenv("API_SECRET_KEY")
    if api_key and secret and api_key != secret:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    try:
        filters = {
            "Domain": domain,
            "Platform": platform,
            "BillingType": billingtype,
            "Type": type,
            "CartRecoveryMode": cartrecoverymode,
        }
        data = get_filtered_data(SHEET_NAME, TAB_NAME, filters)

        if not data:
            raise HTTPException(status_code=404, detail="No data found for the given filters")

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        for row in data:
            writer.writerow(row)

        output.seek(0)
        return StreamingResponse(
            io.BytesIO(output.getvalue().encode('utf-8')), 
            media_type="text/csv", 
            headers={"Content-Disposition": "attachment; filename=leads.csv"}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export leads: {e}")

# ✅ Simple OpenAPI with NO SECURITY
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="MCP CRM API",
        version="1.0.0",
        description="Public CRM API for Claude connection",
        routes=app.routes,
    )

    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "https://airy-renewal-production.up.railway.app",
            "description": "Production server"
        }
    ]

    # ✅ NO SECURITY SCHEMES AT ALL - Make it completely public
    # Remove all security from all endpoints
    for path_name, path_item in openapi_schema["paths"].items():
        for method_name, method_item in path_item.items():
            # Remove any security requirements
            if "security" in method_item:
                del method_item["security"]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Set the custom OpenAPI function
app.openapi = custom_openapi

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
