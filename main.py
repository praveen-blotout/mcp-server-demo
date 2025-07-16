from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import csv
import io

app = FastAPI()

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

# Sheet Configs
SHEET_NAME = "mcp"
TAB_NAME = "Sheet1"

# ✅ API Key Auth Dependency
API_SECRET_KEY = os.getenv("API_SECRET_KEY")

def verify_api_key(x_api_key: str = Header(...)):
    if x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")

# ✅ Utility to fetch filtered leads
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

# ✅ Public health check
@app.get("/")
def read_root():
    return {"message": "✅ Google Sheets MCP Server is running 🚀"}

# ✅ GET leads with filters + auth
@app.get("/crm/leads")
def get_leads(
    domain: Optional[str] = None,
    platform: Optional[str] = None,
    billingtype: Optional[str] = None,
    type: Optional[str] = None,
    cartrecoverymode: Optional[str] = None,
    _: str = Depends(verify_api_key)
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

# ✅ CSV export with filters + auth
@app.get("/crm/leads/export")
def export_leads_csv(
    domain: Optional[str] = None,
    platform: Optional[str] = None,
    billingtype: Optional[str] = None,
    type: Optional[str] = None,
    cartrecoverymode: Optional[str] = None,
    _: str = Depends(verify_api_key)
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

# ✅ Lead model for POST
class Lead(BaseModel):
    name: str
    email: str
    phone: str

# ✅ Add new lead + auth
@app.post("/crm/leads")
def add_lead(lead: Lead, _: str = Depends(verify_api_key)):
    try:
        sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
        sheet.append_row([lead.name, lead.email, lead.phone])
        return {"message": "Lead added successfully ✅"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add lead: {e}")
