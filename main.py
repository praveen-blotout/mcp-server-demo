import asyncio
import json
import sys
import os
from typing import Any, Dict, List, Optional
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Sheets setup
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
google_creds_json = os.getenv("GOOGLE_CLIENT_JSON")

if google_creds_json:
    try:
        creds_dict = json.loads(google_creds_json)
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        SHEET_NAME = "mcp"
        TAB_NAME = "Sheet1"
        USE_GOOGLE_SHEETS = True
    except Exception as e:
        logger.warning(f"Failed to initialize Google Sheets: {e}. Using mock data.")
        USE_GOOGLE_SHEETS = False
else:
    logger.info("No Google credentials provided. Using mock data.")
    USE_GOOGLE_SHEETS = False

# Mock data for when Google Sheets is not available
MOCK_LEADS = [
    {"id": 1, "name": "John Doe", "email": "john@example.com", "phone": "+1234567890", "Domain": "tech", "Platform": "web", "BillingType": "monthly", "Type": "premium", "CartRecoveryMode": "auto"},
    {"id": 2, "name": "Jane Smith", "email": "jane@example.com", "phone": "+1234567891", "Domain": "finance", "Platform": "mobile", "BillingType": "yearly", "Type": "basic", "CartRecoveryMode": "manual"},
    {"id": 3, "name": "Bob Johnson", "email": "bob@example.com", "phone": "+1234567892", "Domain": "tech", "Platform": "web", "BillingType": "monthly", "Type": "premium", "CartRecoveryMode": "auto"},
    {"id": 4, "name": "Alice Brown", "email": "alice@example.com", "phone": "+1234567893", "Domain": "healthcare", "Platform": "web", "BillingType": "yearly", "Type": "enterprise", "CartRecoveryMode": "manual"}
]

class MCPServer:
    def __init__(self):
        self.request_id = None

    async def handle_request(self, request: dict) -> dict:
        """Handle incoming JSON-RPC requests"""
        method = request.get("method")
        params = request.get("params", {})
        self.request_id = request.get("id")
        
        logger.info(f"Received method: {method}")
        
        if method == "initialize":
            return self.handle_initialize(params)
        elif method == "notifications/initialized":
            return None  # No response needed for notification
        elif method == "tools/list":
            return self.handle_tools_list()
        elif method == "tools/call":
            return await self.handle_tool_call(params)
        else:
            return self.error_response(-32601, f"Method not found: {method}")

    def handle_initialize(self, params: dict) -> dict:
        """Handle initialization request"""
        return {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "result": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "crm-mcp-server",
                    "version": "1.0.0"
                }
            }
        }

    def handle_tools_list(self) -> dict:
        """Return list of available tools"""
        return {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "result": {
                "tools": [
                    {
                        "name": "get_crm_leads",
                        "description": "Retrieve CRM leads with optional filtering by domain, platform, billing type, type, and cart recovery mode",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "domain": {
                                    "type": "string",
                                    "description": "Filter by business domain (e.g., tech, finance, healthcare)"
                                },
                                "platform": {
                                    "type": "string",
                                    "description": "Filter by platform (e.g., web, mobile)"
                                },
                                "billingtype": {
                                    "type": "string",
                                    "description": "Filter by billing type (e.g., monthly, yearly)"
                                },
                                "type": {
                                    "type": "string",
                                    "description": "Filter by account type (e.g., basic, premium, enterprise)"
                                },
                                "cartrecoverymode": {
                                    "type": "string",
                                    "description": "Filter by cart recovery mode (e.g., auto, manual)"
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
                        "description": "Add a new lead to the CRM system",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "name": {
                                    "type": "string",
                                    "description": "Full name of the lead"
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
                                    "description": "Business domain",
                                    "default": "unknown"
                                },
                                "platform": {
                                    "type": "string",
                                    "description": "Platform",
                                    "default": "unknown"
                                }
                            },
                            "required": ["name", "email", "phone"]
                        }
                    },
                    {
                        "name": "add_numbers",
                        "description": "Add two numbers together",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "a": {
                                    "type": "number",
                                    "description": "First number"
                                },
                                "b": {
                                    "type": "number",
                                    "description": "Second number"
                                }
                            },
                            "required": ["a", "b"]
                        }
                    }
                ]
            }
        }

    async def handle_tool_call(self, params: dict) -> dict:
        """Handle tool execution"""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        logger.info(f"Tool call: {tool_name} with args: {arguments}")
        
        try:
            if tool_name == "get_crm_leads":
                result = self.get_crm_leads(**arguments)
            elif tool_name == "add_crm_lead":
                result = self.add_crm_lead(**arguments)
            elif tool_name == "add_numbers":
                result = self.add_numbers(**arguments)
            else:
                return self.error_response(-32602, f"Unknown tool: {tool_name}")
            
            return {
                "jsonrpc": "2.0",
                "id": self.request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": result
                        }
                    ]
                }
            }
        except Exception as e:
            logger.error(f"Tool execution error: {e}")
            return self.error_response(-32603, str(e))

    def get_crm_leads(self, domain=None, platform=None, billingtype=None, 
                      type=None, cartrecoverymode=None, limit=10):
        """Get filtered CRM leads"""
        if USE_GOOGLE_SHEETS:
            try:
                sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
                rows = sheet.get_all_records()
                
                # Apply filters
                filtered = []
                for row in rows:
                    if domain and domain.lower() not in str(row.get("Domain", "")).lower():
                        continue
                    if platform and platform.lower() not in str(row.get("Platform", "")).lower():
                        continue
                    if billingtype and billingtype.lower() not in str(row.get("BillingType", "")).lower():
                        continue
                    if type and type.lower() not in str(row.get("Type", "")).lower():
                        continue
                    if cartrecoverymode and cartrecoverymode.lower() not in str(row.get("CartRecoveryMode", "")).lower():
                        continue
                    filtered.append(row)
                
                leads = filtered[:limit]
            except Exception as e:
                logger.error(f"Google Sheets error: {e}")
                leads = MOCK_LEADS
        else:
            # Use mock data
            leads = MOCK_LEADS.copy()
            
            # Apply filters
            if domain:
                leads = [l for l in leads if domain.lower() in l.get("Domain", "").lower()]
            if platform:
                leads = [l for l in leads if platform.lower() in l.get("Platform", "").lower()]
            if billingtype:
                leads = [l for l in leads if billingtype.lower() in l.get("BillingType", "").lower()]
            if type:
                leads = [l for l in leads if type.lower() in l.get("Type", "").lower()]
            if cartrecoverymode:
                leads = [l for l in leads if cartrecoverymode.lower() in l.get("CartRecoveryMode", "").lower()]
            
            leads = leads[:limit]
        
        # Format response
        if not leads:
            return "No leads found matching the specified criteria."
        
        result = f"Found {len(leads)} leads:\n\n"
        for lead in leads:
            result += f"**{lead.get('name', 'N/A')}**\n"
            result += f"- Email: {lead.get('email', 'N/A')}\n"
            result += f"- Phone: {lead.get('phone', 'N/A')}\n"
            result += f"- Domain: {lead.get('Domain', 'N/A')}\n"
            result += f"- Platform: {lead.get('Platform', 'N/A')}\n"
            result += f"- Billing: {lead.get('BillingType', 'N/A')}\n"
            result += f"- Type: {lead.get('Type', 'N/A')}\n"
            result += f"- Cart Recovery: {lead.get('CartRecoveryMode', 'N/A')}\n\n"
        
        return result

    def add_crm_lead(self, name, email, phone, domain="unknown", platform="unknown"):
        """Add a new lead to the CRM"""
        if USE_GOOGLE_SHEETS:
            try:
                sheet = client.open(SHEET_NAME).worksheet(TAB_NAME)
                # Assuming the sheet has these columns in order
                sheet.append_row([name, email, phone, domain, platform, "monthly", "basic", "manual"])
                return f"✅ Lead added successfully!\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nDomain: {domain}\nPlatform: {platform}"
            except Exception as e:
                logger.error(f"Failed to add lead to Google Sheets: {e}")
                return f"❌ Failed to add lead: {str(e)}"
        else:
            # Add to mock data
            new_lead = {
                "id": len(MOCK_LEADS) + 1,
                "name": name,
                "email": email,
                "phone": phone,
                "Domain": domain,
                "Platform": platform,
                "BillingType": "monthly",
                "Type": "basic",
                "CartRecoveryMode": "manual"
            }
            MOCK_LEADS.append(new_lead)
            return f"✅ Lead added successfully!\n\nName: {name}\nEmail: {email}\nPhone: {phone}\nDomain: {domain}\nPlatform: {platform}"

    def add_numbers(self, a, b):
        """Add two numbers together"""
        result = a + b
        return f"The sum of {a} + {b} = {result}"

    def error_response(self, code: int, message: str) -> dict:
        """Create an error response"""
        return {
            "jsonrpc": "2.0",
            "id": self.request_id,
            "error": {
                "code": code,
                "message": message
            }
        }

async def main():
    """Main entry point for the MCP server"""
    server = MCPServer()
    
    logger.info("MCP Server started, waiting for requests...")
    
    # Read from stdin and write to stdout (JSON-RPC over stdio)
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
                
            request = json.loads(line)
            logger.info(f"Received: {request}")
            
            response = await server.handle_request(request)
            
            if response:  # Some notifications don't require a response
                print(json.dumps(response))
                sys.stdout.flush()
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
        except KeyboardInterrupt:
            logger.info("Server stopped by user")
            break
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            error_response = server.error_response(-32603, f"Internal error: {str(e)}")
            print(json.dumps(error_response))
            sys.stdout.flush()

if __name__ == "__main__":
    asyncio.run(main())
