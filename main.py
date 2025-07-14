from fastapi import FastAPI, HTTPException
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = FastAPI()

# Setup scope and auth
scope = [
    "https://spreadsheets.google.com/feeds",
    "https://www.googleapis.com/auth/drive"
]
creds = ServiceAccountCredentials.from_json_keyfile_name("google_client.json", scope)
client = gspread.authorize(creds)

# Connect to your Google Sheet by ID
SHEET_ID = "1PxUi5ZKsMMnzm6cCMMqB8Qc-vGAkRQu5k4ukS1NVaBM"
sheet = client.open_by_key(SHEET_ID).sheet1  # access first tab

@app.get("/")
def root():
    return {"message": "Google Sheet CRM is running 🚀"}

@app.get("/crm/leads")
def get_leads():
    try:
        leads = sheet.get_all_records()
        return {"leads": leads}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
