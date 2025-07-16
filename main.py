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

# API Key Middleware
def verify_api_key(x_api_key: Optional[str] = Header(None)):
    secret = os.getenv("API_SECRET_KEY")
    if not secret:
        raise HTTPException(status_code=500, detail="API secret not configured")
    if x_api_key != secret:
        raise HTTPException(status_code=403, detail="Invalid API key")

# Google Sheets setup
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

# Utility
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

# Models
class Lead(BaseModel):
    name: str
    email: str
    phone: str

# Routes
@app.get("/", dependencies=[Depends(verify_api_key)])
def read_root():
    return {"message": "✅ Google Sheets MCP Server is running 🚀"}

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

        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys() if data else [])
        writer.writeheader()
        for row in data:
            writer.writerow(row)

        output.seek(0)
        return StreamingResponse(output, media_type="text/csv", headers={
            "Content-Disposition": "attachment; filename=leads.csv"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to export leads: {e}")

# 🔧 Custom OpenAPI to match Claude’s expectation
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="MCP CRM API",
        version="1.0.0",
        description="Custom CRM API for Claude connection",
        routes=app.routes,
    )

    openapi_schema["servers"] = [
        {
            "url": "https://airy-renewal-production.up.railway.app",
            "description": "Production server"
        }
    ]

    openapi_schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "name": "x-api-key",
            "in": "header"
        }
    }

    openapi_schema["security"] = [{"APIKeyHeader": []}]
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
