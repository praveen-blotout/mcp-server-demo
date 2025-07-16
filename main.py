from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
import json
import logging
import os
import uuid

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

# ✅ Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"🔵 {request.method} {request.url.path}")
    if request.method == "POST":
        body = await request.body()
        if body:
            try:
                json_body = json.loads(body)
                logger.info(f"🔵 Request body: {json_body}")
            except:
                logger.info(f"🔵 Request body (raw): {body[:200]}...")
    
    # Restore body for processing
    async def receive():
        return {"type": "http.request", "body": body if 'body' in locals() else b""}
    
    request._receive = receive
    response = await call_next(request)
    logger.info(f"🟢 Response: {response.status_code}")
    return response

# ✅ Handle HEAD requests for MCP discovery
@app.head("/")
async def handle_head():
    logger.info("✅ HEAD request for MCP discovery")
    return Response(
        headers={
            "Content-Type": "application/json",
            "X-MCP-Server": "fresh-crm-server/2.0.0"
        }
    )

# ✅ Main MCP endpoint
@app.post("/")
async def handle_mcp_request(request: Request):
    try:
        body = await request.json()
        method = body.get("method")
        request_id = body.get("id")
        params = body.get("params", {})
        
        logger.info(f"✅ MCP Method: {method}")
        
        # Initialize handshake
        if method == "initialize":
            logger.info("🚀 Sending initialize response with tools capability")
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {
                            "listChanged": True
                        }
                    },
                    "serverInfo": {
                        "name": "fresh-crm-server",
                        "version": "2.0.0"
                    }
                }
            }
            logger.info(f"🚀 Initialize response: {json.dumps(response, indent=2)}")
            return JSONResponse(response)
        
        # List available tools
        elif method == "tools/list":
            logger.info("🔧 Sending tools list...")
            tools_response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "get_crm_leads",
                            "description": "Retrieve leads from the CRM system with optional filtering",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "domain": {
                                        "type": "string",
                                        "description": "Filter leads by business domain (tech, finance, healthcare, etc.)"
                                    },
                                    "platform": {
                                        "type": "string", 
                                        "description": "Filter leads by platform (web, mobile, etc.)"
                                    },
                                    "limit": {
                                        "type": "integer",
                                        "description": "Maximum number of leads to return",
                                        "minimum": 1,
                                        "maximum": 100,
                                        "default": 10
                                    }
                                }
                            }
                        },
                        {
                            "name": "add_crm_lead",
                            "description": "Add a new lead to the CRM system",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "name": {
                                        "type": "string",
                                        "description": "Full name of the potential customer"
                                    },
                                    "email": {
                                        "type": "string",
                                        "description": "Email address of the lead"
                                    },
                                    "phone": {
                                        "type": "string",
                                        "description": "Phone number of the lead"
                                    },
                                    "domain": {
                                        "type": "string",
                                        "description": "Business domain/industry of the lead",
                                        "default": "unknown"
                                    }
                                },
                                "required": ["name", "email", "phone"]
                            }
                        }
                    ]
                }
            }
            logger.info(f"🔧 Tools response: {json.dumps(tools_response, indent=2)}")
            return JSONResponse(tools_response)
        
        # Execute tool calls
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            
            logger.info(f"🔧 Tool call: {tool_name} with args: {tool_args}")
            
            if tool_name == "get_crm_leads":
                # Filter leads
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
                    result_text += f"  Email: {lead['email']}\n"
                    result_text += f"  Phone: {lead['phone']}\n"
                    result_text += f"  Domain: {lead['domain']} | Platform: {lead['platform']}\n\n"
                
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
                
                if not all([name, email, phone]):
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32602,
                            "message": "Missing required fields: name, email, and phone are required"
                        }
                    })
                
                new_lead = {
                    "id": len(MOCK_LEADS) + 1,
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "domain": domain,
                    "platform": "unknown"
                }
                MOCK_LEADS.append(new_lead)
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"✅ **Lead Added Successfully!**\n\n**Name:** {name}\n**Email:** {email}\n**Phone:** {phone}\n**Domain:** {domain}\n\nThe lead has been added to the CRM system."
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
                        "message": f"Unknown tool: {tool_name}"
                    }
                })
        
        # Handle notifications (no response needed)
        elif method == "notifications/initialized":
            logger.info("✅ Client initialized notification received")
            return Response(status_code=200)
        
        else:
            logger.warning(f"❓ Unknown method: {method}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            })
    
    except Exception as e:
        logger.error(f"❌ Error processing MCP request: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id if 'request_id' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }, status_code=500)

# ✅ Regular endpoints for testing
@app.get("/")
async def root():
    return {
        "message": "Fresh MCP CRM Server v2.0", 
        "status": "ready",
        "server": "fresh-crm-server",
        "version": "2.0.0",
        "protocol": "MCP 2025-06-18"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy", 
        "type": "mcp-server",
        "tools_available": 2,
        "leads_count": len(MOCK_LEADS)
    }

# ✅ Debug endpoint
@app.get("/debug")
async def debug():
    return {
        "server_info": {
            "name": "fresh-crm-server",
            "version": "2.0.0",
            "protocol": "MCP 2025-06-18"
        },
        "available_tools": [
            "get_crm_leads",
            "add_crm_lead"
        ],
        "sample_data": MOCK_LEADS[:2]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
