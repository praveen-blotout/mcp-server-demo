from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Dict, Any, List, Optional
from datetime import datetime

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

# Google Sheets setup
USE_GOOGLE_SHEETS = False
client = None
SHEET_NAME = "mcp"
TAB_NAME = "Sheet1"

google_creds_json = os.getenv("GOOGLE_CLIENT_JSON")
if google_creds_json:
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds_dict = json.loads(google_creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        USE_GOOGLE_SHEETS = True
        logger.info("✅ Google Sheets connected successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Google Sheets client: {e}")

# Track if we've sent tools to this session
tools_sent = set()

def get_filtered_data(filters: dict = {}) -> List[dict]:
    """Get filtered data from Google Sheets"""
    if not USE_GOOGLE_SHEETS or not client:
        return []
    
    try:
        sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
        rows = sheet.get_all_records()
        logger.info(f"Retrieved {len(rows)} records from Google Sheets")
        
        filtered = []
        for row in rows:
            match = True
            for key, value in filters.items():
                if value:
                    if value.lower() not in str(row.get(key, "")).lower():
                        match = False
                        break
            if match:
                filtered.append(row)
        
        return filtered
    except Exception as e:
        logger.error(f"Error fetching data: {e}")
        return []

@app.post("/")
async def handle_mcp_request(request: Request):
    """MCP handler that aggressively sends tools"""
    try:
        body = await request.json()
        method = body.get("method")
        request_id = body.get("id")
        params = body.get("params", {})
        
        # Get session identifier
        session_id = str(params.get("clientInfo", {}).get("name", "unknown"))
        
        logger.info(f"📨 MCP Method: {method} (session: {session_id})")
        
        if method == "initialize":
            logger.info("🚀 Initialize - declaring tools capability")
            
            # Clear this session's tools sent status
            tools_sent.discard(session_id)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "crm-mcp-server",
                        "version": "8.0.0"
                    }
                }
            })
            
        elif method == "notifications/initialized":
            logger.info("✅ Client initialized")
            
            # HACK: Immediately follow up with tools list
            if session_id not in tools_sent:
                tools_sent.add(session_id)
                logger.info("🎯 Proactively sending tools list notification")
                
                # Send a custom response that includes tool information
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "method": "tools/update",
                    "params": {
                        "tools": [
                            {
                                "name": "get_crm_leads",
                                "description": "Get CRM leads (filters: platform=SHOPIFY/WOOCOMMERCE, billingtype=USAGE/CONTRACT, type=1P/2P)"
                            },
                            {
                                "name": "add_crm_lead",
                                "description": "Add lead (params: teamname, domain, platform)"
                            }
                        ]
                    }
                })
            
            return Response(status_code=200)
            
        elif method == "tools/list":
            logger.info("🔧 TOOLS LIST CALLED! Sending tools...")
            tools_sent.add(session_id)
            
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "tools": [
                        {
                            "name": "get_crm_leads",
                            "description": "Retrieve leads from Google Sheets CRM. Filters: platform (WOOCOMMERCE/SHOPIFY/EDGETAG/BIGCOMMERCE/SALESFORCE), billingtype (USAGE/SHOPIFY/CONTRACT/FREE), type (1P/2P), cartrecoverymode (N/A/disabled/enabled), providers (klaviyo/facebook/etc)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "platform": {
                                        "type": "string",
                                        "description": "Filter by platform"
                                    },
                                    "billingtype": {
                                        "type": "string",
                                        "description": "Filter by billing type"
                                    },
                                    "type": {
                                        "type": "string",
                                        "description": "Filter by type (1P or 2P)"
                                    },
                                    "cartrecoverymode": {
                                        "type": "string",
                                        "description": "Filter by cart recovery mode"
                                    },
                                    "providers": {
                                        "type": "string",
                                        "description": "Filter by provider (partial match)"
                                    },
                                    "limit": {
                                        "type": "integer",
                                        "description": "Max results (default 10)",
                                        "default": 10
                                    }
                                }
                            }
                        },
                        {
                            "name": "add_crm_lead",
                            "description": "Add a new lead to Google Sheets",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "teamname": {
                                        "type": "string",
                                        "description": "Team name"
                                    },
                                    "domain": {
                                        "type": "string",
                                        "description": "Domain"
                                    },
                                    "platform": {
                                        "type": "string",
                                        "description": "Platform (SHOPIFY/WOOCOMMERCE/etc)"
                                    }
                                },
                                "required": ["teamname", "domain", "platform"]
                            }
                        }
                    ]
                }
            })
            
        elif method == "resources/list":
            logger.info("📚 Resources list requested")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "resources": []  # No resources for this server
                }
            })
            
        elif method == "prompts/list":
            logger.info("💬 Prompts list requested")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "prompts": []  # No prompts for this server
                }
            })
            
        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            logger.info(f"🔧 Tool call: {tool_name} with args: {tool_args}")
            
            if tool_name == "get_crm_leads":
                if not USE_GOOGLE_SHEETS:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": "❌ Google Sheets not connected. Set GOOGLE_CLIENT_JSON environment variable in Railway."
                            }]
                        }
                    })
                
                # Build filters - handle both lowercase and proper case
                filters = {}
                
                # Platform filter
                platform = tool_args.get("platform") or tool_args.get("Platform")
                if platform:
                    filters["Platform"] = platform
                
                # BillingType filter  
                billingtype = tool_args.get("billingtype") or tool_args.get("BillingType")
                if billingtype:
                    filters["BillingType"] = billingtype
                
                # Type filter
                type_filter = tool_args.get("type") or tool_args.get("Type")
                if type_filter:
                    filters["Type"] = type_filter
                
                # CartRecoveryMode filter
                cartmode = tool_args.get("cartrecoverymode") or tool_args.get("CartRecoveryMode")
                if cartmode:
                    filters["CartRecoveryMode"] = cartmode
                
                # Providers filter
                providers = tool_args.get("providers") or tool_args.get("Providers")
                if providers:
                    filters["Providers"] = providers
                
                logger.info(f"Applying filters: {filters}")
                
                leads = get_filtered_data(filters)
                limit = tool_args.get("limit", 10)
                leads = leads[:limit]
                
                if not leads:
                    result_text = f"No leads found with filters: {filters}\n\n"
                    if not USE_GOOGLE_SHEETS:
                        result_text += "Note: Google Sheets is not connected."
                    else:
                        result_text += "Check if:\n1. Sheet 'mcp' exists\n2. Tab 'Sheet1' exists\n3. Data matches your filter criteria"
                else:
                    result_text = f"Found {len(leads)} leads"
                    if filters:
                        result_text += f" (filtered by: {', '.join([f'{k}={v}' for k,v in filters.items()])})"
                    result_text += ":\n\n"
                    
                    for i, lead in enumerate(leads, 1):
                        result_text += f"**{i}. {lead.get('TeamName', 'N/A')}**\n"
                        result_text += f"   • Domain: {lead.get('Domain', 'N/A')}\n"
                        result_text += f"   • Platform: {lead.get('Platform', 'N/A')}\n"
                        result_text += f"   • Billing: {lead.get('BillingType', 'N/A')}\n"
                        result_text += f"   • Type: {lead.get('Type', 'N/A')}\n"
                        result_text += f"   • Cart Recovery: {lead.get('CartRecoveryMode', 'N/A')}\n"
                        result_text += f"   • Revenue: ${lead.get('Revenue', '0')}\n"
                        if i < len(leads):
                            result_text += "\n"
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{
                            "type": "text",
                            "text": result_text
                        }]
                    }
                })
            
            elif tool_name == "add_crm_lead":
                if not USE_GOOGLE_SHEETS:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": "❌ Cannot add lead: Google Sheets not connected."
                            }]
                        }
                    })
                
                try:
                    sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
                    new_row = [
                        "",  # TagId
                        tool_args.get("teamname", ""),
                        tool_args.get("domain", ""),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "", "",  # Versions, LastDeployment
                        tool_args.get("platform", ""),
                        "Active",
                        "", "", "",  # OperationType, Providers, Plugins
                        "CONTRACT",
                        "1P",
                        "",  # Contacts
                        "N/A",  # CartRecoveryMode
                        "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0",
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    ]
                    sheet.append_row(new_row)
                    
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [{
                                "type": "text",
                                "text": f"✅ Lead added: {tool_args.get('teamname')} ({tool_args.get('domain')})"
                            }]
                        }
                    })
                except Exception as e:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": f"Failed to add lead: {str(e)}"
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
        
        elif method == "ping":
            logger.info("🏓 Ping received")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "status": "pong",
                    "timestamp": datetime.now().isoformat()
                }
            })
            
        # Handle unknown methods
        else:
            logger.warning(f"Unknown method: {method}")
            return JSONResponse({
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            })
            
    except json.JSONDecodeError:
        # Handle empty or invalid requests
        logger.warning("Received invalid JSON or empty request")
        return JSONResponse({"error": "Invalid request"}, status_code=400)
    except Exception as e:
        logger.error(f"Error: {e}")
        return JSONResponse({
            "jsonrpc": "2.0",
            "id": request_id if 'request_id' in locals() else None,
            "error": {
                "code": -32603,
                "message": f"Internal error: {str(e)}"
            }
        }, status_code=500)

@app.get("/")
async def root():
    return {
        "type": "MCP Server",
        "version": "8.0.0",
        "status": "ready",
        "google_sheets": "connected" if USE_GOOGLE_SHEETS else "not connected",
        "instructions": "Use Claude's MCP tools: get_crm_leads and add_crm_lead"
    }

@app.head("/")
async def head_root():
    """Support HEAD requests"""
    return Response(status_code=200)

# Ignore OAuth endpoints that Claude is looking for
@app.get("/.well-known/{path:path}")
async def ignore_wellknown(path: str):
    return JSONResponse({"error": "Not implemented"}, status_code=404)

@app.post("/register")
async def ignore_register():
    return JSONResponse({"error": "Not implemented"}, status_code=404)

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting MCP Server on port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
