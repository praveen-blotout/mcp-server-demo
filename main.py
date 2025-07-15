from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import gspread
from oauth2client.service_account import ServiceAccountCredentials

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

@app.get("/")
def read_root():
    return {"message": "✅ Google Sheets MCP Server is running 🚀"}

@app.get("/crm/leads")
def get_leads(
    domain: Optional[str] = None,
    platform: Optional[str] = None,
    billingtype: Optional[str] = None,
    type: Optional[str] = None,
    cartrecoverymode: Optional[str] = None
):
    try:
        sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
        rows = sheet.get_all_records()

        filtered_rows = []
        for row in rows:
            if domain and domain.lower() not in row.get("Domain", "").lower():
                continue
            if platform and platform.lower() not in row.get("Platform", "").lower():
                continue
            if billingtype and billingtype.lower() not in row.get("BillingType", "").lower():
                continue
            if type and type.lower() not in row.get("Type", "").lower():
                continue
            if cartrecoverymode and cartrecoverymode.lower() not in row.get("CartRecoveryMode", "").lower():
                continue
            filtered_rows.append(row)

        if not filtered_rows:
            return JSONResponse(content={"headers": [], "rows": []})

        headers = list(filtered_rows[0].keys())
        rows = [list(item.values()) for item in filtered_rows]

        return JSONResponse(content={"headers": headers, "rows": rows})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch leads: {e}")


class Lead(BaseModel):
    name: str
    email: str
    phone: str

@app.post("/crm/leads")
def add_lead(lead: Lead):
    try:
        sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
        sheet.append_row([lead.name, lead.email, lead.phone])
        return {"message": "Lead added successfully ✅"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add lead: {e}")
