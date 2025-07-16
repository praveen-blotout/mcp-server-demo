from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Union
import json
import logging
import os

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

# ✅ MCP Server Info
MCP_SERVER_INFO = {
    "name": "crm-server",
    "version": "1.0.0",
    "description": "CRM data server for Claude",
    "capabilities": {
        "tools": {},
        "resources": {}
    }
}

# ✅ Mock CRM data
MOCK_LEADS = [
    {"id": 1, "name": "John Doe", "email": "john@example.com", "phone": "+1234567890", "domain": "tech", "platform": "web"},
    {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "phone": "+1234567891", "domain": "finance", "platform": "mobile"},
    {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "phone": "+1234567892", "domain": "tech", "platform": "web"},
    {"id": 4, "name": "Alice Brown", "email": "alice@example.com", "phone": "+1234567893", "domain": "healthcare", "platform": "web"}
]

# ✅ MCP Request/Response Models
class MCPRequest(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None  # Can be string, int, or None
    method: str
    params: Optional[Dict[str, Any]] = None

class MCPResponse(BaseModel):
    jsonrpc: str = "2.0"
    id: Optional[Any] = None  # Can be string, int, or None
    result: Optional[Dict[str, Any]] = None
    error: Optional[Dict[str, Any]] = None

# ✅ Handle HEAD requests (MCP discovery)
@app.head("/")
async def handle_head():
    return Response(
        headers={
            "X-MCP-Server": "crm-server/1.0.0",
            "Content-Type": "application/json"
        }
    )

# ✅ Handle MCP registration
@app.post("/register")
async def register():
    logger.info("✅ MCP Registration request")
    return JSONResponse({
        "jsonrpc": "2.0",
        "result": {
            "server": MCP_SERVER_INFO,
            "capabilities": {
                "tools": {
                    "get_leads": {
                        "description": "Get CRM leads with optional filters",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "domain": {"type": "string", "description": "Filter by domain"},
                                "platform": {"type": "string", "description": "Filter by platform"},
                                "limit": {"type": "integer", "description": "Maximum number of results"}
                            }
                        }
                    },
                    "add_lead": {
                        "description": "Add a new lead to the CRM",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "name": {"type": "string", "description": "Lead name"},
                                "email": {"type": "string", "description": "Lead email"},
                                "phone": {"type": "string", "description": "Lead phone number"}
                            },
                            "required": ["name", "email", "phone"]
                        }
                    }
                }
            }
        }
    })

# ✅ Main MCP endpoint
@app.post("/")
async def handle_mcp_request(request: Request):
    try:
        body = await request.json()
        logger.info(f"✅ MCP Request: {body}")
        
        mcp_request = MCPRequest(**body)
        
        if mcp_request.method == "initialize":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": mcp_request.id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {},
                        "resources": {}
                    },
                    "serverInfo": MCP_SERVER_INFO
                }
            })
        
        elif mcp_request.method == "tools/list":
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": mcp_request.id,
                "result": {
                    "tools": [
                        {
                            "name": "get_leads",
                            "description": "Get CRM leads with optional filters",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "domain": {"type": "string", "description": "Filter by domain"},
                                    "platform": {"type": "string", "description": "Filter by platform"},
                                    "limit": {"type": "integer", "description": "Maximum number of results", "default": 10}
                                }
                            }
                        },
                        {
                            "name": "add_lead",
                            "description": "Add a new lead to the CRM",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string", "description": "Lead name"},
                                    "email": {"type": "string", "description": "Lead email"},
                                    "phone": {"type": "string", "description": "Lead phone number"}
                                },
                                "required": ["name", "email", "phone"]
                            }
                        }
                    ]
                }
            })
        
        elif mcp_request.method == "tools/call":
            tool_name = mcp_request.params.get("name")
            tool_args = mcp_request.params.get("arguments", {})
            
            if tool_name == "get_leads":
                # Filter leads based on arguments
                filtered_leads = MOCK_LEADS.copy()
                
                if "domain" in tool_args:
                    domain = tool_args["domain"].lower()
                    filtered_leads = [lead for lead in filtered_leads if domain in lead["domain"].lower()]
                
                if "platform" in tool_args:
                    platform = tool_args["platform"].lower()
                    filtered_leads = [lead for lead in filtered_leads if platform in lead["platform"].lower()]
                
                limit = tool_args.get("limit", 10)
                filtered_leads = filtered_leads[:limit]
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": mcp_request.id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Found {len(filtered_leads)} leads:\n\n" + 
                                       "\n".join([f"• {lead['name']} ({lead['email']}) - {lead['domain']}/{lead['platform']}" 
                                                for lead in filtered_leads])
                            }
                        ],
                        "isError": False
                    }
                })
            
            elif tool_name == "add_lead":
                name = tool_args.get("name")
                email = tool_args.get("email")
                phone = tool_args.get("phone")
                
                if not all([name, email, phone]):
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": mcp_request.id,
                        "error": {
                            "code": -32602,
                            "message": "Missing required fields: name, email, phone"
                        }
                    })
                
                new_lead = {
                    "id": len(MOCK_LEADS) + 1,
                    "name": name,
                    "email": email,
                    "phone": phone,
                    "domain": "unknown",
                    "platform": "unknown"
                }
                MOCK_LEADS.append(new_lead)
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": mcp_request.id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"✅ Successfully added lead: {name} ({email})"
                            }
                        ],
                        "isError": False
                    }
                })
            
            else:
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": mcp_request.id,
                    "error": {
                        "code": -32601,
                        "message": f"Unknown tool: {tool_name}"
                    }
                })
        
        else:
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": mcp_request.id,
                "error": {
                    "code": -32601,
                    "message": f"Unknown method: {mcp_request.method}"
                }
            })
    
    except Exception as e:
        logger.error(f"❌ Error processing MCP request: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": getattr(mcp_request, 'id', None) if 'mcp_request' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }, status_code=500)

# ✅ Regular HTTP endpoints for testing
@app.get("/")
async def root():
    return {"message": "MCP CRM Server", "status": "ready"}

@app.get("/health")
async def health():
    return {"status": "healthy", "type": "mcp-server"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
