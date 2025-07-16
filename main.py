from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional, Dict, Any
import json
import logging

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

# ✅ Mock CRM data
MOCK_LEADS = [
    {"id": 1, "name": "John Doe", "email": "john@example.com", "phone": "+1234567890", "domain": "tech", "platform": "web"},
    {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "phone": "+1234567891", "domain": "finance", "platform": "mobile"},
    {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "phone": "+1234567892", "domain": "tech", "platform": "web"},
    {"id": 4, "name": "Alice Brown", "email": "alice@example.com", "phone": "+1234567893", "domain": "healthcare", "platform": "web"}
]

# Global flag to track initialization
initialized = False

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"🔵 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"🟢 Response: {response.status_code}")
    return response

@app.head("/")
async def handle_head():
    logger.info("✅ HEAD request - MCP discovery")
    return Response(headers={"Content-Type": "application/json"})

@app.post("/")
async def handle_mcp_request(request: Request):
    global initialized
    try:
        body = await request.json()
        method = body.get("method")
        request_id = body.get("id")
        params = body.get("params", {})
        
        logger.info(f"📨 MCP Request: {method}")
        logger.info(f"📨 Full body: {json.dumps(body, indent=2)}")
        
        if method == "initialize":
            logger.info("🚀 Handling initialize...")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "super-crm-server",
                        "version": "3.0.0"
                    }
                }
            }
            logger.info(f"🚀 Initialize response: {json.dumps(response, indent=2)}")
            return JSONResponse(response)
            
        elif method == "notifications/initialized":
            logger.info("✅ Client initialized - setting server as ready")
            initialized = True
            return Response(status_code=200)
            
        elif method == "tools/list":
            logger.info("🔧 Tools list requested!")
            if not initialized:
                logger.warning("❌ Tools list called before initialization complete")
            
            response = {
                "jsonrpc": "2.0", 
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "get_crm_leads",
                            "description": "Get leads from CRM with optional filters",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "domain": {"type": "string", "description": "Filter by domain"},
                                    "platform": {"type": "string", "description": "Filter by platform"},
                                    "limit": {"type": "integer", "description": "Max results", "default": 10}
                                }
                            }
                        },
                        {
                            "name": "add_crm_lead", 
                            "description": "Add new lead to CRM",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Lead name"},
                                    "email": {"type": "string", "description": "Lead email"},
                                    "phone": {"type": "string", "description": "Lead phone"}
                                },
                                "required": ["name", "email", "phone"]
                            }
                        }
                    ]
                }
            }
            logger.info(f"🔧 Tools response: {json.dumps(response, indent=2)}")
            return JSONResponse(response)
            
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            logger.info(f"🔧 Calling tool: {tool_name} with {tool_args}")
            
            if tool_name == "get_crm_leads":
                filtered = MOCK_LEADS.copy()
                
                if "domain" in tool_args:
                    domain = tool_args["domain"].lower()
                    filtered = [l for l in filtered if domain in l["domain"].lower()]
                
                if "platform" in tool_args:  
                    platform = tool_args["platform"].lower()
                    filtered = [l for l in filtered if platform in l["platform"].lower()]
                    
                limit = tool_args.get("limit", 10)
                filtered = filtered[:limit]
                
                result = f"Found {len(filtered)} leads:\n\n"
                for lead in filtered:
                    result += f"• {lead['name']} ({lead['email']}) - {lead['domain']}/{lead['platform']}\n"
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id, 
                    "result": {
                        "content": [{"type": "text", "text": result}]
                    }
                })
                
            elif tool_name == "add_crm_lead":
                name = tool_args.get("name")
                email = tool_args.get("email") 
                phone = tool_args.get("phone")
                
                if not all([name, email, phone]):
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32602, "message": "Missing required fields"}
                    })
                
                new_lead = {
                    "id": len(MOCK_LEADS) + 1,
                    "name": name, "email": email, "phone": phone,
                    "domain": "unknown", "platform": "unknown"
                }
                MOCK_LEADS.append(new_lead)
                
                return JSONResponse({
                    "jsonrpc": "2.0", 
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": f"✅ Added: {name} ({email})"}]
                    }
                })
            
            else:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id, 
                    "error": {"code": -32601, "message": f"Unknown tool: {tool_name}"}
                })
        
        else:
            logger.warning(f"❓ Unknown method: {method}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown method: {method}"}
            })
            
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        return JSONResponse({
            "jsonrpc": "2.0", 
            "id": request_id if 'request_id' in locals() else None,
            "error": {"code": -32603, "message": str(e)}
        })

@app.get("/")
async def root():
    return {"message": "Super CRM MCP Server v3.0", "status": "ready", "initialized": initialized}

@app.get("/health") 
async def health():
    return {"status": "healthy", "leads": len(MOCK_LEADS), "initialized": initialized}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
