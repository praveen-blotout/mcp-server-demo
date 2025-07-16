from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
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

# Mock CRM data
MOCK_LEADS = [
    {"id": 1, "name": "John Doe", "email": "john@example.com", "phone": "+1234567890", "domain": "tech", "platform": "web"},
    {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "phone": "+1234567891", "domain": "finance", "platform": "mobile"},
    {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "phone": "+1234567892", "domain": "tech", "platform": "web"},
    {"id": 4, "name": "Alice Brown", "email": "alice@example.com", "phone": "+1234567893", "domain": "healthcare", "platform": "web"}
]

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"🔵 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"🟢 Response: {response.status_code}")
    return response

@app.post("/")
async def handle_mcp_request(request: Request):
    try:
        body = await request.json()
        method = body.get("method")
        request_id = body.get("id")
        params = body.get("params", {})
        
        logger.info(f"📨 MCP Method: {method}")
        
        if method == "initialize":
            logger.info("🚀 Initialize - declaring tools capability")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {},
                        "resources": False,
                        "prompts": False
                    },
                    "serverInfo": {
                        "name": "final-crm-server",
                        "version": "4.0.0"
                    }
                }
            })
            
        elif method == "notifications/initialized":
            logger.info("✅ Client initialized")
            # Some MCP clients need a hint about available tools
            logger.info("🎯 Sending tools hint in initialized response")
            return JSONResponse({
                "jsonrpc": "2.0",
                "method": "notifications/tools/changed",
                "params": {}
            })
            
        elif method == "methods/list":
            logger.info("📋 Methods list requested")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "methods": [
                        "initialize",
                        "tools/list",
                        "tools/call"
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
                                        "description": "Filter leads by business domain (e.g., tech, finance, healthcare)"
                                    },
                                    "platform": {
                                        "type": "string",
                                        "description": "Filter leads by platform (e.g., web, mobile)"
                                    },
                                    "limit": {
                                        "type": "integer",
                                        "description": "Maximum number of leads to return (default: 10)",
                                        "minimum": 1,
                                        "maximum": 100,
                                        "default": 10
                                    }
                                },
                                "additionalProperties": False
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
                                        "description": "Business domain (e.g., tech, finance, healthcare)",
                                        "default": "unknown"
                                    },
                                    "platform": {
                                        "type": "string", 
                                        "description": "Platform (e.g., web, mobile)",
                                        "default": "unknown"
                                    }
                                },
                                "required": ["name", "email", "phone"],
                                "additionalProperties": False
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
                filtered_leads = MOCK_LEADS.copy()
                
                if "domain" in tool_args:
                    domain = tool_args["domain"].lower()
                    filtered_leads = [lead for lead in filtered_leads if domain in lead["domain"].lower()]
                
                if "platform" in tool_args:
                    platform = tool_args["platform"].lower()
                    filtered_leads = [lead for lead in filtered_leads if platform in lead["platform"].lower()]
                
                limit = min(tool_args.get("limit", 10), 100)
                filtered_leads = filtered_leads[:limit]
                
                result_text = f"Found {len(filtered_leads)} leads:\n\n"
                for lead in filtered_leads:
                    result_text += f"• **{lead['name']}**\n"
                    result_text += f"  📧 {lead['email']}\n"
                    result_text += f"  📞 {lead['phone']}\n"
                    result_text += f"  🏢 {lead['domain']} | 📱 {lead['platform']}\n\n"
                
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
                domain = tool_args.get("domain", "unknown")
                platform = tool_args.get("platform", "unknown")
                
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
                                "text": f"✅ **Lead Added Successfully!**\n\n📝 **Name:** {name}\n📧 **Email:** {email}\n📞 **Phone:** {phone}\n🏢 **Domain:** {domain}\n📱 **Platform:** {platform}\n\nThe lead has been added to the CRM system with ID #{new_lead['id']}."
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
    return {
        "message": "Final CRM MCP Server v4.0", 
        "status": "ready",
        "tools": ["get_crm_leads", "add_crm_lead"],
        "leads_count": len(MOCK_LEADS)
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "version": "4.0.0"}

# Debug endpoint to manually check tools
@app.get("/debug/tools")
async def debug_tools():
    return {
        "tools": [
            {
                "name": "get_crm_leads",
                "description": "Get CRM leads with filters",
                "params": ["domain", "platform", "limit"]
            },
            {
                "name": "add_crm_lead", 
                "description": "Add new lead to CRM",
                "params": ["name", "email", "phone", "domain", "platform"]
            }
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
