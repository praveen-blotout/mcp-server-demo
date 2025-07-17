from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import logging
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from typing import Dict, Any, List, Optional
import csv
import io
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
        USE_GOOGLE_SHEETS = False

# Filter options
PLATFORM_OPTIONS = ["WOOCOMMERCE", "SHOPIFY", "EDGETAG", "BIGCOMMERCE", "SALESFORCE"]
BILLING_TYPE_OPTIONS = ["USAGE", "SHOPIFY", "CONTRACT", "FREE"]
TYPE_OPTIONS = ["1P", "2P"]
CART_RECOVERY_MODE_OPTIONS = ["N/A", "disabled", "enabled", "preview", "ab-test"]
PROVIDER_OPTIONS = [
    "attentive", "bing", "blotoutWallet", "customersAI", "facebook", 
    "gcpPubSub", "googleAdsClicks", "googleAnalytics4", "klaviyo", 
    "outOfTheBlue", "pinterest", "reddit", "shopGPT", "shopify", 
    "snapchat", "tiktok", "yotpo"
]

def get_filtered_data(filters: dict = {}) -> List[dict]:
    """Filter data using case-insensitive partial matching"""
    if USE_GOOGLE_SHEETS and client:
        try:
            sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
            rows = sheet.get_all_records()
            logger.info(f"✅ Fetched {len(rows)} records from Google Sheets")
        except Exception as e:
            logger.error(f"Failed to fetch from Google Sheets: {e}")
            return []
    else:
        logger.warning("⚠️ Google Sheets not connected. Please set GOOGLE_CLIENT_JSON environment variable.")
        return []
    
    filtered = []
    for row in rows:
        match = True
        for key, value in filters.items():
            if value:
                # Special handling for Providers field (partial match)
                if key == "Providers" and value:
                    providers_field = str(row.get(key, "")).lower()
                    if value.lower() not in providers_field:
                        match = False
                        break
                # For other fields, use case-insensitive partial matching
                elif value.lower() not in str(row.get(key, "")).lower():
                    match = False
                    break
        if match:
            filtered.append(row)
    
    return filtered

def format_lead_response(leads: List[dict]) -> str:
    """Format leads for display"""
    if not leads:
        return "No leads found matching the specified criteria. Please ensure the Google Sheets connection is configured and contains data."
    
    result = f"Found {len(leads)} leads:\n\n"
    
    for i, lead in enumerate(leads, 1):
        result += f"**{i}. {lead.get('TeamName', 'N/A')} (Tag: {lead.get('TagId', 'N/A')})**\n"
        result += f"   - Domain: {lead.get('Domain', 'N/A')}\n"
        result += f"   - Platform: {lead.get('Platform', 'N/A')}\n"
        result += f"   - Status: {lead.get('Status', 'N/A')}\n"
        result += f"   - Billing Type: {lead.get('BillingType', 'N/A')}\n"
        result += f"   - Type: {lead.get('Type', 'N/A')}\n"
        result += f"   - Cart Recovery: {lead.get('CartRecoveryMode', 'N/A')}\n"
        result += f"   - Revenue: {lead.get('Revenue', 'N/A')}\n"
        result += f"   - Potential Revenue: {lead.get('PotentialRevenue', 'N/A')}\n"
        result += f"   - Created: {lead.get('CreatedAt', 'N/A')}\n"
        if lead.get('Providers'):
            result += f"   - Providers: {lead.get('Providers', 'N/A')}\n"
        result += "\n"
    
    return result

@app.middleware("http")
async def log_requests(request: Request, call_next):
    logger.info(f"🔵 {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"🟢 Response: {response.status_code}")
    return response

@app.post("/simple")
async def simple_endpoint(request: Request):
    """Simple endpoint for when MCP tools disconnect"""
    try:
        body = await request.json()
        action = body.get("action", "").lower()
        
        logger.info(f"Simple endpoint called with action: {action}")
        
        if "help" in action or not action:
            return JSONResponse({
                "message": "CRM Commands: 'get leads', 'get shopify leads', 'get contract billing leads', 'add lead [name] [domain] [platform]'",
                "status": "ready"
            })
        
        elif "get" in action and "lead" in action:
            filters = {}
            
            # Parse filters from action
            if "shopify" in action:
                filters["Platform"] = "SHOPIFY"
            if "woocommerce" in action:
                filters["Platform"] = "WOOCOMMERCE"
            if "contract" in action:
                filters["BillingType"] = "CONTRACT"
            if "usage" in action:
                filters["BillingType"] = "USAGE"
            if "1p" in action:
                filters["Type"] = "1P"
            if "2p" in action:
                filters["Type"] = "2P"
            
            leads = get_filtered_data(filters)[:10]
            
            if not leads:
                return JSONResponse({
                    "message": "No leads found. Make sure Google Sheets is connected.",
                    "connected": USE_GOOGLE_SHEETS
                })
            
            response = f"Found {len(leads)} leads:\n"
            for lead in leads:
                response += f"- {lead.get('TeamName')} ({lead.get('Domain')}) - {lead.get('Platform')}\n"
            
            return JSONResponse({"message": response})
        
        else:
            return JSONResponse({
                "message": "Try: 'get leads' or 'get shopify leads'",
                "status": "ready"
            })
            
    except Exception as e:
        logger.error(f"Simple endpoint error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/")
async def handle_mcp_request(request: Request):
    """MCP handler for Claude"""
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
                        "tools": {}
                    },
                    "serverInfo": {
                        "name": "crm-mcp-server",
                        "version": "7.0.0"
                    }
                }
            })
            
        elif method == "notifications/initialized":
            logger.info("✅ Client initialized")
            # Try to force tool discovery by sending a notification
            logger.info("🎯 Attempting to trigger tool discovery...")
            
            # Return a hint about available tools
            return JSONResponse({
                "jsonrpc": "2.0",
                "result": {
                    "hint": "Tools available: get_crm_leads, add_crm_lead. Use tools/list to discover them.",
                    "tools_ready": True
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
                            "description": "Retrieve leads from Google Sheets CRM with filtering options. Filters: platform (WOOCOMMERCE/SHOPIFY/EDGETAG/BIGCOMMERCE/SALESFORCE), billingtype (USAGE/SHOPIFY/CONTRACT/FREE), type (1P/2P), cartrecoverymode (N/A/disabled/enabled/preview/ab-test), providers (partial match)",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "platform": {
                                        "type": "string",
                                        "description": "Filter by platform: WOOCOMMERCE, SHOPIFY, EDGETAG, BIGCOMMERCE, SALESFORCE",
                                        "enum": ["WOOCOMMERCE", "SHOPIFY", "EDGETAG", "BIGCOMMERCE", "SALESFORCE"]
                                    },
                                    "billingtype": {
                                        "type": "string",
                                        "description": "Filter by billing type: USAGE, SHOPIFY, CONTRACT, FREE",
                                        "enum": ["USAGE", "SHOPIFY", "CONTRACT", "FREE"]
                                    },
                                    "type": {
                                        "type": "string",
                                        "description": "Filter by type: 1P or 2P",
                                        "enum": ["1P", "2P"]
                                    },
                                    "cartrecoverymode": {
                                        "type": "string",
                                        "description": "Filter by cart recovery mode: N/A, disabled, enabled, preview, ab-test",
                                        "enum": ["N/A", "disabled", "enabled", "preview", "ab-test"]
                                    },
                                    "providers": {
                                        "type": "string",
                                        "description": "Filter by provider (partial match): attentive, bing, blotoutWallet, customersAI, facebook, gcpPubSub, googleAdsClicks, googleAnalytics4, klaviyo, outOfTheBlue, pinterest, reddit, shopGPT, shopify, snapchat, tiktok, yotpo"
                                    },
                                    "domain": {
                                        "type": "string",
                                        "description": "Filter by domain (partial match)"
                                    },
                                    "limit": {
                                        "type": "integer",
                                        "description": "Maximum number of leads to return",
                                        "default": 10
                                    }
                                }
                            }
                        },
                        {
                            "name": "add_crm_lead",
                            "description": "Add a new lead to the Google Sheets CRM",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "teamname": {
                                        "type": "string",
                                        "description": "Team name"
                                    },
                                    "domain": {
                                        "type": "string",
                                        "description": "Domain name"
                                    },
                                    "platform": {
                                        "type": "string",
                                        "description": "Platform: WOOCOMMERCE, SHOPIFY, EDGETAG, BIGCOMMERCE, SALESFORCE",
                                        "enum": ["WOOCOMMERCE", "SHOPIFY", "EDGETAG", "BIGCOMMERCE", "SALESFORCE"]
                                    },
                                    "billingtype": {
                                        "type": "string",
                                        "description": "Billing type: USAGE, SHOPIFY, CONTRACT, FREE",
                                        "enum": ["USAGE", "SHOPIFY", "CONTRACT", "FREE"],
                                        "default": "CONTRACT"
                                    },
                                    "type": {
                                        "type": "string",
                                        "description": "Type: 1P or 2P",
                                        "enum": ["1P", "2P"],
                                        "default": "1P"
                                    },
                                    "contacts": {
                                        "type": "string",
                                        "description": "Contact information"
                                    }
                                },
                                "required": ["teamname", "domain", "platform"]
                            }
                        },
                        {
                            "name": "export_crm_leads",
                            "description": "Export filtered leads to CSV format",
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
                                        "description": "Filter by type"
                                    },
                                    "cartrecoverymode": {
                                        "type": "string",
                                        "description": "Filter by cart recovery mode"
                                    },
                                    "providers": {
                                        "type": "string",
                                        "description": "Filter by provider"
                                    }
                                }
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
                # Build filters
                filters = {}
                if tool_args.get("platform"):
                    filters["Platform"] = tool_args["platform"]
                if tool_args.get("billingtype"):
                    filters["BillingType"] = tool_args["billingtype"]
                if tool_args.get("type"):
                    filters["Type"] = tool_args["type"]
                if tool_args.get("cartrecoverymode"):
                    filters["CartRecoveryMode"] = tool_args["cartrecoverymode"]
                if tool_args.get("providers"):
                    filters["Providers"] = tool_args["providers"]
                if tool_args.get("domain"):
                    filters["Domain"] = tool_args["domain"]
                
                limit = tool_args.get("limit", 10)
                
                # Get filtered data
                leads = get_filtered_data(filters)
                if limit and limit > 0:
                    leads = leads[:limit]
                
                # Format response
                result_text = format_lead_response(leads)
                
                if not USE_GOOGLE_SHEETS:
                    result_text = "⚠️ **Google Sheets not connected!**\n\nThe server is not connected to Google Sheets. Please ensure:\n1. GOOGLE_CLIENT_JSON environment variable is set on Railway\n2. The service account has access to your Google Sheet\n3. The sheet name is 'mcp' with tab 'Sheet1'\n\nCurrently returning empty results."
                
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
                if not USE_GOOGLE_SHEETS:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "❌ Cannot add lead: Google Sheets not connected. Please configure GOOGLE_CLIENT_JSON environment variable."
                                }
                            ]
                        }
                    })
                
                try:
                    sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
                    
                    # Prepare row data based on column order
                    new_row = [
                        "",  # TagId (auto-generated or empty)
                        tool_args.get("teamname", ""),
                        tool_args.get("domain", ""),
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S"),  # CreatedAt
                        "",  # Versions
                        "",  # LastDeployment
                        tool_args.get("platform", ""),
                        "Active",  # Status (default)
                        "",  # OperationType
                        "",  # Providers
                        "",  # Plugins
                        tool_args.get("billingtype", "CONTRACT"),
                        tool_args.get("type", "1P"),
                        tool_args.get("contacts", ""),
                        "N/A",  # CartRecoveryMode (default)
                        "0",  # Purchases
                        "0",  # Revenue
                        "0",  # LiveCarts
                        "0",  # PotentialRevenue
                        "0",  # CartExpiredPassiveUsers
                        "0",  # LostRevenuePassiveUsers
                        "0",  # CartExpiredActiveUsers
                        "0",  # LostRevenueActiveUsers
                        "0",  # EngagedVisitors
                        "0",  # CartsRestored
                        "0",  # RestoredValue
                        "0",  # EmailsCaptured
                        "0",  # TotalRecoveryPurchasesCount
                        "0",  # TotalRecoveryPurchaseValue
                        datetime.now().strftime("%Y-%m-%d %H:%M:%S")  # Created time
                    ]
                    
                    sheet.append_row(new_row)
                    
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"✅ **Lead Added Successfully!**\n\n**Details:**\n- Team: {tool_args.get('teamname')}\n- Domain: {tool_args.get('domain')}\n- Platform: {tool_args.get('platform')}\n- Billing: {tool_args.get('billingtype', 'CONTRACT')}\n- Type: {tool_args.get('type', '1P')}\n- Contacts: {tool_args.get('contacts', 'N/A')}"
                                }
                            ]
                        }
                    })
                except Exception as e:
                    logger.error(f"Failed to add lead: {e}")
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {
                            "code": -32603,
                            "message": f"Failed to add lead: {str(e)}"
                        }
                    })
            
            elif tool_name == "export_crm_leads":
                # Build filters
                filters = {}
                for key in ["platform", "billingtype", "type", "cartrecoverymode", "providers"]:
                    if tool_args.get(key):
                        filter_key = key.capitalize()
                        if key == "billingtype":
                            filter_key = "BillingType"
                        elif key == "cartrecoverymode":
                            filter_key = "CartRecoveryMode"
                        elif key == "providers":
                            filter_key = "Providers"
                        filters[filter_key] = tool_args[key]
                
                leads = get_filtered_data(filters)
                
                if not leads:
                    return JSONResponse({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": "No leads found to export with the specified filters."
                                }
                            ]
                        }
                    })
                
                # Create CSV content
                csv_content = "TagId,TeamName,Domain,Platform,BillingType,Type,CartRecoveryMode,Revenue,Contacts\n"
                for lead in leads:
                    csv_content += f"{lead.get('TagId', '')},{lead.get('TeamName', '')},{lead.get('Domain', '')},{lead.get('Platform', '')},{lead.get('BillingType', '')},{lead.get('Type', '')},{lead.get('CartRecoveryMode', '')},{lead.get('Revenue', '')},{lead.get('Contacts', '')}\n"
                
                return JSONResponse({
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"✅ Exported {len(leads)} leads to CSV format:\n\n```csv\n{csv_content[:500]}{'...' if len(csv_content) > 500 else ''}\n```\n\n(Showing first 500 characters)"
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
        "message": "CRM MCP Server v7.0", 
        "status": "ready",
        "google_sheets_connected": USE_GOOGLE_SHEETS,
        "sheet_name": SHEET_NAME if USE_GOOGLE_SHEETS else "Not connected",
        "tools": ["get_crm_leads", "add_crm_lead", "export_crm_leads"],
        "endpoints": {
            "mcp": "POST /",
            "simple": "POST /simple",
            "direct_tool": "POST /tool/{tool_name}"
        },
        "filters": {
            "platform": PLATFORM_OPTIONS,
            "billingtype": BILLING_TYPE_OPTIONS,
            "type": TYPE_OPTIONS,
            "cartrecoverymode": CART_RECOVERY_MODE_OPTIONS,
            "providers": PROVIDER_OPTIONS
        }
    }

@app.get("/tool/list")
@app.post("/tool/list")
async def tool_list_endpoint():
    """Direct endpoint to list tools"""
    return JSONResponse({
        "tools": [
            {
                "name": "get_crm_leads",
                "description": "Get leads with filters",
                "filters": ["platform", "billingtype", "type", "cartrecoverymode", "providers"]
            },
            {
                "name": "add_crm_lead",
                "description": "Add new lead",
                "required": ["teamname", "domain", "platform"]
            }
        ],
        "available_filters": {
            "platform": PLATFORM_OPTIONS,
            "billingtype": BILLING_TYPE_OPTIONS,
            "type": TYPE_OPTIONS,
            "cartrecoverymode": CART_RECOVERY_MODE_OPTIONS
        }
    })

@app.post("/tool/{tool_name}")
async def direct_tool_call(tool_name: str, request: Request):
    """Direct tool invocation endpoint"""
    try:
        body = await request.json() if request.headers.get("content-type") == "application/json" else {}
        
        logger.info(f"Direct tool call: {tool_name} with args: {body}")
        
        if tool_name == "get_crm_leads":
            filters = {}
            for key in ["Platform", "BillingType", "Type", "CartRecoveryMode", "Providers", "Domain"]:
                if body.get(key.lower()):
                    filters[key] = body[key.lower()]
            
            leads = get_filtered_data(filters)
            limit = body.get("limit", 10)
            leads = leads[:limit] if limit else leads
            
            return JSONResponse({
                "success": True,
                "count": len(leads),
                "data": leads,
                "message": format_lead_response(leads)
            })
        
        elif tool_name == "list":
            return JSONResponse({
                "tools": [
                    {"name": "get_crm_leads", "endpoint": "/tool/get_crm_leads"},
                    {"name": "add_crm_lead", "endpoint": "/tool/add_crm_lead"}
                ]
            })
        
        else:
            return JSONResponse({"error": f"Unknown tool: {tool_name}"}, status_code=404)
            
    except Exception as e:
        logger.error(f"Direct tool error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health():
    return {
        "status": "healthy", 
        "version": "7.0.0",
        "google_sheets_connected": USE_GOOGLE_SHEETS
    }

if __name__ == "__main__":
    import uvicorn
    logger.info("🚀 Starting CRM MCP Server on port 8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
