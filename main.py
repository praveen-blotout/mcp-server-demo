from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.openapi.utils import get_openapi
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import csv
import io

app = FastAPI()

# ✅ API Key Verification Dependency
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    secret = os.getenv("API_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=500, detail="API secret not configured")
    if x_api_key != secret:
        raise HTTPException(status_code=403, detail="Invalid API key")

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

# ✅ Public endpoint for Claude connection testing
@app.get("/")
def read_root():
    """Public endpoint for basic connectivity check"""
    return {"message": "✅ Google Sheets MCP Server is running 🚀", "status": "healthy"}

# ✅ Test connection endpoint with query parameter auth
@app.get("/test-connection")
def test_connection(api_key: Optional[str] = None):
    """Test endpoint for Claude to verify API key without header auth"""
    secret = os.getenv("API_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=500, detail="API secret not configured")
    if api_key != secret:
        raise HTTPException(status_code=403, detail="Invalid API key - use ?api_key=YOUR_KEY")
    return {"status": "connected", "message": "Authentication successful", "server": "ready"}

# ✅ Protected Routes with header authentication
@app.get("/crm/leads", dependencies=[Depends(verify_api_key)])
def get_leads(
    domain: Optional[str] = None,
    platform: Optional[str] = None,
    billingtype: Optional[str] = None,
    type: Optional[str] = None,
    cartrecoverymode: Optional[str] = None
):
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

@app.post("/crm/leads", dependencies=[Depends(verify_api_key)])
def add_lead(lead: Lead):
    try:
        sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
        sheet.append_row([lead.name, lead.email, lead.phone])
        return {"message": "Lead added successfully ✅"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add lead: {e}")

@app.get("/crm/leads/export", dependencies=[Depends(verify_api_key)])
def export_leads_csv(
    domain: Optional[str] = None,
    platform: Optional[str] = None,
    billingtype: Optional[str] = None,
    type: Optional[str] = None,
    cartrecoverymode: Optional[str] = None
):
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

# ✅ Alternative endpoints with query parameter auth (if header auth doesn't work)
@app.get("/crm/leads/query-auth")
def get_leads_query_auth(
    api_key: str,
    domain: Optional[str] = None,
    platform: Optional[str] = None,
    billingtype: Optional[str] = None,
    type: Optional[str] = None,
    cartrecoverymode: Optional[str] = None
):
    """Alternative endpoint with query parameter authentication"""
    secret = os.getenv("API_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=500, detail="API secret not configured")
    if api_key != secret:
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

# ✅ Custom OpenAPI Schema with proper security handling
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="MCP CRM API",
        version="1.0.0",
        description="Custom CRM API for Claude connection",
        routes=app.routes,
    )

    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "https://airy-renewal-production.up.railway.app",
            "description": "Production server"
        }
    ]

    # Add security schemes
    if "components" not in openapi_schema:
        openapi_schema["components"] = {}
    
    openapi_schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "name": "x-api-key",
            "in": "header"
        },
        "APIKeyQuery": {
            "type": "apiKey",
            "name": "api_key",
            "in": "query"
        }
    }

    # Add global security for most endpoints
    openapi_schema["security"] = [{"APIKeyHeader": []}]

    # Remove auto-generated x-api-key parameters from endpoints
    for path_name, path_item in openapi_schema["paths"].items():
        for method_name, method_item in path_item.items():
            if "parameters" in method_item:
                # Filter out x-api-key header parameters
                method_item["parameters"] = [
                    param for param in method_item["parameters"]
                    if not (param.get("name") == "x-api-key" and param.get("in") == "header")
                ]
                # Remove empty parameters list
                if not method_item["parameters"]:
                    del method_item["parameters"]

    # Make specific endpoints public (no auth required)
    public_endpoints = ["/", "/test-connection"]
    for endpoint in public_endpoints:
        if endpoint in openapi_schema["paths"]:
            for method in openapi_schema["paths"][endpoint]:
                openapi_schema["paths"][endpoint][method]["security"] = []

    # Set query auth endpoints to use query parameter security
    query_auth_endpoints = ["/crm/leads/query-auth"]
    for endpoint in query_auth_endpoints:
        if endpoint in openapi_schema["paths"]:
            for method in openapi_schema["paths"][endpoint]:
                openapi_schema["paths"][endpoint][method]["security"] = [{"APIKeyQuery": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

# Set the custom OpenAPI function
app.openapi = custom_openapi

# ✅ Health check endpoint
@app.get("/health")
def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "MCP CRM API"}

# ✅ API info endpoint
@app.get("/info")
def api_info():
    """API information endpoint"""
    return {
        "name": "MCP CRM API",
        "version": "1.0.0",
        "description": "Custom CRM API for Claude connection",
        "endpoints": {
            "public": ["/", "/health", "/info", "/test-connection"],
            "authenticated": ["/crm/leads", "/crm/leads/export"],
            "alternative_auth": ["/crm/leads/query-auth"]
        },
        "authentication": {
            "header": "x-api-key",
            "query_param": "api_key (for alternative endpoints)"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
