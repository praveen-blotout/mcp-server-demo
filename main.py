from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.openapi.utils import get_openapi
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
import os
import json
import logging
import time
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# ✅ Add CORS middleware - Very permissive for debugging
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    # Log the incoming request
    logger.info(f"🔵 INCOMING REQUEST: {request.method} {request.url}")
    logger.info(f"🔵 Headers: {dict(request.headers)}")
    logger.info(f"🔵 Client IP: {request.client.host if request.client else 'Unknown'}")
    
    # Process the request
    response = await call_next(request)
    
    # Log the response
    process_time = time.time() - start_time
    logger.info(f"🟢 RESPONSE: {response.status_code} | Time: {process_time:.3f}s")
    
    return response

# ✅ Models
class Lead(BaseModel):
    name: str
    email: str
    phone: str

# ✅ Completely public endpoints
@app.get("/")
def read_root():
    logger.info("✅ Root endpoint accessed")
    return {
        "message": "✅ Google Sheets MCP Server is running 🚀", 
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "endpoints": [
            "/",
            "/openapi.json", 
            "/docs",
            "/health",
            "/test"
        ]
    }

@app.get("/health")
def health_check():
    logger.info("✅ Health endpoint accessed")
    return {
        "status": "healthy",
        "service": "MCP CRM API",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/test")
def test_endpoint():
    logger.info("✅ Test endpoint accessed")
    return {
        "status": "success",
        "message": "Test endpoint working",
        "timestamp": datetime.now().isoformat()
    }

# ✅ Mock data endpoint (no Google Sheets dependency)
@app.get("/crm/leads")
def get_leads_mock(
    domain: Optional[str] = None,
    platform: Optional[str] = None,
    limit: Optional[int] = 10
):
    logger.info(f"✅ Leads endpoint accessed with filters: domain={domain}, platform={platform}")
    
    # Return mock data for testing
    mock_data = [
        {"id": 1, "name": "John Doe", "email": "john@example.com", "domain": "tech", "platform": "web"},
        {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "domain": "finance", "platform": "mobile"},
        {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "domain": "tech", "platform": "web"}
    ]
    
    # Apply filters if provided
    filtered_data = mock_data
    if domain:
        filtered_data = [item for item in filtered_data if domain.lower() in item["domain"].lower()]
    if platform:
        filtered_data = [item for item in filtered_data if platform.lower() in item["platform"].lower()]
    
    # Apply limit
    if limit:
        filtered_data = filtered_data[:limit]
    
    return JSONResponse(content={
        "data": filtered_data,
        "count": len(filtered_data),
        "filters_applied": {"domain": domain, "platform": platform},
        "timestamp": datetime.now().isoformat()
    })

@app.post("/crm/leads")
def add_lead_mock(lead: Lead):
    logger.info(f"✅ Add lead endpoint accessed with data: {lead.model_dump()}")
    return {
        "message": "Lead added successfully ✅", 
        "lead": lead.model_dump(),
        "timestamp": datetime.now().isoformat()
    }

# ✅ Very simple OpenAPI - no security at all
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Debug MCP CRM API",
        version="1.0.0",
        description="Debug version of CRM API for Claude connection testing",
        routes=app.routes,
    )

    # Add servers
    openapi_schema["servers"] = [
        {
            "url": "https://airy-renewal-production.up.railway.app",
            "description": "Production server"
        }
    ]

    # Remove all security requirements
    for path_name, path_item in openapi_schema["paths"].items():
        for method_name, method_item in path_item.items():
            if "security" in method_item:
                del method_item["security"]
    
    # Remove global security if it exists
    if "security" in openapi_schema:
        del openapi_schema["security"]
    
    # Remove security schemes
    if "components" in openapi_schema and "securitySchemes" in openapi_schema["components"]:
        del openapi_schema["components"]["securitySchemes"]

    logger.info("✅ OpenAPI schema generated")
    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi

# ✅ Add docs endpoint for debugging
@app.get("/debug")
def debug_info():
    return {
        "message": "Debug information",
        "openapi_url": "/openapi.json",
        "docs_url": "/docs",
        "endpoints": [
            "GET /",
            "GET /health", 
            "GET /test",
            "GET /crm/leads",
            "POST /crm/leads",
            "GET /openapi.json"
        ],
        "timestamp": datetime.now().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
