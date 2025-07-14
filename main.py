from fastapi import FastAPI, HTTPException
import requests
import os
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

API_TOKEN = os.getenv("SEATABLE_API_TOKEN")
BASE_URL = os.getenv("SEATABLE_BASE_URL")            # Use https://cloud.seatable.io
BASE_UUID = os.getenv("SEATABLE_BASE_UUID")          # Example: 000414eb-ebac-4fa9-ab3e-c26c0061db87

def get_headers():
    return {
        "Authorization": f"Token {API_TOKEN}",
        "Accept": "application/json"
    }

@app.get("/")
def home():
    return {"message": "SeaTable MCP Server is running 🚀"}

@app.get("/crm/leads")
def get_leads():
    try:
        url = f"{BASE_URL}/api-gateway/api/v2/dtables/{BASE_UUID}/rows/?table_name=praveen"
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/crm/schema")
def get_schema():
    try:
        url = f"{BASE_URL}/api/v2.1/dtable/{BASE_UUID}/tables/"
        response = requests.get(url, headers=get_headers())
        response.raise_for_status()
        return response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
