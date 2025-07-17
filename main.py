from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
from typing import Dict, Any

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

# Mock CRM data
MOCK_LEADS = [
    {"id": 1, "name": "John Doe", "email": "john@example.com", "phone": "+1234567890", "domain": "tech", "platform": "web"},
    {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "phone": "+1234567891", "domain": "finance", "platform": "mobile"},
    {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "phone": "+1234567892", "domain": "tech", "platform": "web"},
    {"id": 4, "name": "Alice Brown", "email": "alice@example.com", "phone": "+1234567893", "domain": "healthcare", "platform": "web"}
]

# Store initialized state
initialized_sessions = set()

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"🔵 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"🟢 Response: {response.status_code}")
    return response

async def get_request_body(request: Request) -> Dict[str, Any]:
    """Safely get request body"""
    try:
        return await request.json()
    except:
        return {}

@app.post("/")
async def handle_mcp_request(request: Request):
    """Enhanced MCP handler that proactively sends tools"""
    try:
        body = await get_request_body(request)
        method = body.get("method")
        request_id = body.get("id")
        params = body.get("params", {})
        
        logger.info(f"📨 MCP Method: {method}")
        logger.info(f"📋 Full request: {json.dumps(body, indent=2)}")
        
        # Track session ID from client info
        session_id = None
        if method == "initialize":
            client_info = params.get("clientInfo", {})
            session_id = f"{client_info.get('name', 'unknown')}_{client_info.get('version', '0')}"
        
        if method == "initialize":
            logger.info("🚀 Initialize - declaring tools capability")
            
            # Mark this session as initialized
            if session_id:
                initialized_sessions.add(session_id)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {},
                        "experimental": {
                            "autoToolDiscovery": True
                        }
                    },
                    "serverInfo": {
                        "name": "crm-mcp-server",
                        "version": "5.0.0"
                    }
                }
            })
            
        elif method == "notifications/initialized":
            logger.info("✅ Client initialized")
            
            # HACK: Send tools list proactively since Claude web doesn't request it
            logger.info("🎯 Proactively sending tools list")
            
            # Send the tools as a response with a special format
            return JSONResponse({
                "jsonrpc": "2.0",
                "method": "tools/available",
                "params": {
                    "tools": [
                        {
                            "name": "get_crm_leads",
                            "description": "Get CRM leads with optional filters"
                        },
                        {
                            "name": "add_crm_lead",
                            "description": "Add a new lead to CRM"
                        }
                    ]
                }
            })
            
        elif method == "tools/list":
            logger.info("🔧 TOOLS LIST CALLED! Sending tools...")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "get_crm_leads",
                            "description": "Retrieve leads from the CRM system with optional filtering by domain and platform",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "domain": {
                                        "type": "string",
                                        "description": "Filter leads by business domain (e.g., tech, finance, healthcare)",
                                        "enum": ["tech", "finance", "healthcare", "all"]
                                    },
                                    "platform": {
                                        "type": "string", 
                                        "description": "Filter leads by platform (e.g., web, mobile)",
                                        "enum": ["web", "mobile", "all"]
                                    },
                                    "limit": {
                                        "type": "integer",
                                        "description": "Maximum number of leads to return (default: 10)",
                                        "minimum": 1,
                                        "maximum": 100,
                                        "default": 10
                                    }
                                }
                            }
                        },
                        {
                            "name": "add_crm_lead",
                            "description": "Add a new lead to the CRM system with name, email, and phone number",
                            "inputSchema": {
                                "type": "object", 
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Full name of the lead"
                                    },
                                    "email": {
                                        "type": "string",
                                        "description": "Email address of the lead",
                                        "format": "email"
                                    },
                                    "phone": {
                                        "type": "string",
                                        "description": "Phone number of the lead"
                                    },
                                    "domain": {
                                        "type": "string",
                                        "description": "Business domain",
                                        "enum": ["tech", "finance", "healthcare"],
                                        "default": "tech"
                                    },
                                    "platform": {
                                        "type": "string",
                                        "description": "Platform",
                                        "enum": ["web", "mobile"],
                                        "default": "web"
                                    }
                                },
                                "required": ["name", "email", "phone"]
                            }
                        }
                    ]
                }
            })
            
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            logger.info(f"🔧 Tool call: {tool_name} with args: {tool_args}")
            
            if tool_name == "get_crm_leads":
                # Get parameters
                domain_filter = tool_args.get("domain", "all")
                platform_filter = tool_args.get("platform", "all")
                limit = min(tool_args.get("limit", 10), 100)
                
                # Filter leads
                filtered_leads = MOCK_LEADS.copy()
                
                if domain_filter != "all":
                    filtered_leads = [l for l in filtered_leads if l["domain"] == domain_filter]
                
                if platform_filter != "all":
                    filtered_leads = [l for l in filtered_leads if l["platform"] == platform_filter]
                
                filtered_leads = filtered_leads[:limit]
                
                # Format response
                result_text = f"Found {len(filtered_leads)} leads"
                if domain_filter != "all" or platform_filter != "all":
                    filters = []
                    if domain_filter != "all":
                        filters.append(f"domain={domain_filter}")
                    if platform_filter != "all":
                        filters.append(f"platform={platform_filter}")
                    result_text += f" (filtered by: {', '.join(filters)})"
                result_text += ":\n\n"
                
                for lead in filtered_leads:
                    result_text += f"**{lead['name']}**\n"
                    result_text += f"📧 Email: {lead['email']}\n"
                    result_text += f"📞 Phone: {lead['phone']}\n"
                    result_text += f"🏢 Domain: {lead['domain']}\n"
                    result_text += f"📱 Platform: {lead['platform']}\n\n"
                
                if not filtered_leads:
                    result_text = "No leads found matching the specified criteria."
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": result_text
                            }
                        ]
                    }
                })
            
            elif tool_name == "add_crm_lead":
                name = tool_args.get("name")
                email = tool_args.get("email")
                phone = tool_args.get("phone")
                domain = tool_args.get("domain", "tech")
                platform = tool_args.get("platform", "web")
                
                if not all([name, email, phone]):
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": "Missing required parameters. Name, email, and phone are all required."
                        }
                    })
                
                new_lead = {
                    "id": len(MOCK_LEADS) + 1,
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "domain": domain,
                    "platform": platform
                }
                MOCK_LEADS.append(new_lead)
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"✅ **Lead Added Successfully!**\n\n**Details:**\n- Name: {name}\n- Email: {email}\n- Phone: {phone}\n- Domain: {domain}\n- Platform: {platform}\n\nThe lead has been added to the CRM system with ID #{new_lead['id']}."
                            }
                        ]
                    }
                })
            
            else:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}. Available tools: get_crm_leads, add_crm_lead"
                    }
                })
        
        # Handle other methods
        elif method in ["initialized", "ping"]:
            return Response(status_code=200)
            
        else:
            logger.warning(f"❓ Unknown method: {method}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method '{method}' not found"
                }
            })
            
    except Exception as e:
        logger.error(f"❌ Error processing request: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id if 'request_id' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal server error: {str(e)}"
            }
        }, status_code=500)

@app.get("/")
async def root():
    """Status endpoint"""
    return {
        "message": "CRM MCP Server v5.0", 
        "status": "ready",
        "type": "MCP Server",
        "tools": ["get_crm_leads", "add_crm_lead"],
        "leads_count": len(MOCK_LEADS),
        "instructions": "Connect via Claude custom connector"
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "5.0.0", "leads": len(MOCK_LEADS)}

# Debug endpoints
@app.get("/debug/leads")
async def debug_leads():
    """View all current leads"""
    return {"leads": MOCK_LEADS, "count": len(MOCK_LEADS)}

@app.post("/debug/tools/list")
async def debug_tools_list():
    """Manually trigger tools list"""
    return {
        "jsonrpc": "2.0",
        "id": "debug",
        "result": {
            "tools": [
                {"name": "get_crm_leads", "description": "Get CRM leads"},
                {"name": "add_crm_lead", "description": "Add new lead"}
            ]
        }
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting CRM MCP Server on port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
