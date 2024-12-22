import os
import json
import logging
from typing import Any

import aiohttp
from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    Tool,
    TextContent
)
from mcp.server.stdio import stdio_server

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)  # Set to DEBUG for detailed logs
logger = logging.getLogger("os_hub_service")

# API configuration
API_KEY = os.getenv("OPEN_SUPPLY_HUB_API_KEY")
if not API_KEY:
    raise ValueError("OPEN_SUPPLY_HUB_API_KEY environment variable required")

API_BASE_URL = "https://staging.opensupplyhub.org/api"

class OSHubServer(Server):
    def __init__(self, name: str):
        super().__init__(name)
        self._initialized = False

    async def initialize(self, options) -> dict:
        """Handle server initialization"""
        logger.info("Starting initialization...")
        try:
            # Test API connection
            headers = {
                "Authorization": f"Token {API_KEY}",
                 "Accept": "application/json"  # Explicitly request JSON
            }
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}?q=test", headers=headers) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Failed to fetch data: {response.status}")
            
            self._initialized = True
            logger.info("Server initialization complete")
            
            # Return initialization result with detailed capabilities
            return {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {
                        "search_production_locations": {
                            "description": "Search for production locations by query in Open Supply Hub.",
                            "command": "search_production_locations"
                        }
                    },
                    "resources": {},  # Empty object if no resources
                    "prompts": {
                        "example_prompt": {
                            "description": "An example prompt",
                            "options": ["option1", "option2"]
                        }
                    }
                },
                "serverInfo": {
                    "name": self.name,
                    "version": "1.0.0"
                }
            }
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    async def search_production_locations(self, query: str) -> dict[str, Any]:
        """Search production location data from Open Supply Hub API."""
        if not self._initialized:
            raise RuntimeError("Server is not initialized")
        
        logger.debug(f"Fetching production locations with query: {query}")
        headers = {
                "Authorization": f"Token {API_KEY}",
                 "Accept": "application/json"  # Explicitly request JSON
        }
        
        url = f"{API_BASE_URL}/v1/production-locations/"
        params = {'query': query}
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers) as response:
                logger.debug(f"Received response: {response.status}")
                if response.status != 200:
                    raise RuntimeError(f"Failed to fetch data: {response.status}")
                data = await response.json()
                logger.debug(f"Response JSON: {data}")
                return data
            
    async def fetch_production_location_by_id(self, os_id: str) -> dict[str, Any]:
        """Fetch detailed information for a specific production location by OS ID."""
        if not self._initialized:
            raise RuntimeError("Server is not initialized")

        logger.debug(f"Fetching production location details for OS ID: {os_id}")
        headers = {
            "Authorization": f"Token {API_KEY}",
            "Accept": "application/json"  # Explicitly request JSON
        }
        url = f"{API_BASE_URL}/v1/production-locations/{os_id}/"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                logger.debug(f"Received response: {response.status}")
                if response.status == 404:
                    raise ValueError(f"Production location with OS ID {os_id} not found")
                if response.status != 200:
                    raise RuntimeError(f"Failed to fetch production location details: {response.status}")
                data = await response.json()
                logger.debug(f"Response JSON: {data}")
                return data
            
    async def create_production_location(self, location_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new production location in Open Supply Hub."""
        if not self._initialized:
            raise RuntimeError("Server is not initialized")

        logger.debug("Submitting new production location")
        headers = {
            "Authorization": f"Token {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        url = f"{API_BASE_URL}/v1/production-locations/"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=location_data) as response:
                logger.debug(f"Received response: {response.status}")
                
                if response.status == 202:  # Accepted, as per the specification
                    data = await response.json()
                    logger.debug(f"Location submission response: {data}")
                    return data
                elif response.status == 401:
                    raise PermissionError("Unauthorized. Check your API key.")
                elif response.status == 422:
                    error_data = await response.json()
                    raise ValueError(f"Validation error: {error_data}")
                else:
                    raise RuntimeError(f"Failed to submit location: {response.status}")

    async def moderate_production_location(self, moderation_id: str) -> dict[str, Any]:
        """Create a new production location based on a moderation event."""
        if not self._initialized:
            raise RuntimeError("Server is not initialized")

        logger.debug(f"Moderating production location for moderation ID: {moderation_id}")
        headers = {
            "Authorization": f"Token {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        url = f"{API_BASE_URL}/v1/moderation-events/{moderation_id}/production-locations/"

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers) as response:
                logger.debug(f"Received response: {response.status}")
                
                if response.status == 201:  # Created
                    data = await response.json()
                    logger.debug(f"Production location creation response: {data}")
                    return data
                elif response.status == 401:
                    raise PermissionError("Unauthorized. Check your API key.")
                elif response.status == 403:
                    raise PermissionError("Forbidden. User may not be confirmed.")
                elif response.status == 404:
                    raise ValueError(f"Moderation event {moderation_id} not found")
                elif response.status == 410:
                    raise ValueError("Moderation event is not in PENDING status")
                else:
                    raise RuntimeError(f"Failed to moderate location: {response.status}")

    async def contribute_to_production_location(self, os_id: str, contribution_data: dict[str, Any]) -> dict[str, Any]:
        """Contribute additional information to an existing production location."""
        if not self._initialized:
            raise RuntimeError("Server is not initialized")

        logger.debug(f"Contributing to production location: {os_id}")
        headers = {
            "Authorization": f"Token {API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        url = f"{API_BASE_URL}/v1/production-locations/{os_id}/"

        async with aiohttp.ClientSession() as session:
            async with session.patch(url, headers=headers, json=contribution_data) as response:
                logger.debug(f"Received response: {response.status}")
                
                if response.status == 202:  # Accepted
                    data = await response.json()
                    logger.debug(f"Contribution response: {data}")
                    return data
                elif response.status == 401:
                    raise PermissionError("Unauthorized. Check your API key.")
                elif response.status == 403:
                    raise PermissionError("Forbidden. User may not be confirmed.")
                elif response.status == 404:
                    raise ValueError(f"Production location {os_id} not found")
                else:
                    raise RuntimeError(f"Failed to contribute to location: {response.status}")            
        
# Initialize the server
app = OSHubServer("os_hub_server")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="search_production_locations",
            description="Search for production locations by query in Open Supply Hub.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query string to search for production locations."
                    }
                },
                "required": ["query"]
            },
        ),
        Tool(
            name="fetch_production_location_by_id",
            description="Get detailed information for a specific production location by OS ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "os_id": {
                        "type": "string",
                        "description": "The Open Supply Hub ID of the production location(e.g., GB123)."
                    }
                },
                "required": ["os_id"]
            },
        ),
        Tool(
            name="create_production_location",
            description="Submit a new production location to Open Supply Hub.",
            inputSchema={
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Name of the production location"
                    },
                    "address": {
                        "type": "string",
                        "description": "Address of the production location"
                    },
                    "country": {
                        "type": "string",
                        "description": "Country code (alpha-2)"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the production location"
                    },
                    "sector": {
                        "type": "string",
                        "description": "Sector of the production location"
                    },
                    "product_type": {
                        "type": "string",
                        "description": "Type of products manufactured"
                    },
                    "parent_company": {
                        "type": "string",
                        "description": "Name of the parent company"
                    }
                },
                "required": ["name", "country"]
            },
        ),
        Tool(
            name="moderate_production_location",
            description="Create a new production location based on a moderation event.",
            inputSchema={
                "type": "object",
                "properties": {
                    "moderation_id": {
                        "type": "string",
                        "description": "The unique identifier of the moderation event"
                    }
                },
                "required": ["moderation_id"]
            },
        ),
        Tool(
            name="contribute_to_production_location",
            description="Add additional information to an existing production location.",
            inputSchema={
                "type": "object",
                "properties": {
                    "os_id": {
                        "type": "string",
                        "description": "The unique identifier of the production location"
                    },
                    "name": {
                        "type": "string",
                        "description": "Name of the production location"
                    },
                    "address": {
                        "type": "string",
                        "description": "Address of the production location"
                    },
                    "description": {
                        "type": "string",
                        "description": "Description of the production location"
                    },
                    "sector": {
                        "type": "string",
                        "description": "Sector of the production location"
                    },
                    "product_type": {
                        "type": "string",
                        "description": "Type of products manufactured"
                    }
                },
                "required": ["os_id"]
            }
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    if name == "search_production_locations":
        query = arguments.get("query", "")
        
        try:
            data = await app.search_production_locations(query)
            
            # Format the response to include count and production locations
            formatted_response = {
                "total_count": data.get('count', 0),
                "facilities": data.get('data', [])
            }
            
            return [TextContent(type="text", text=json.dumps(formatted_response, indent=2))]
        except Exception as e:
            logger.error(f"Error searching prodution locations: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "fetch_production_location_by_id":
        os_id = arguments.get("os_id", "")
        if not os_id:
            raise ValueError("Missing 'os_id' in arguments.")
        try:
            data = await app.fetch_production_location_by_id(os_id)
            return [TextContent(type="text", text=json.dumps(data, indent=2))]
        except ValueError as e:
            # Handle not found case
            return [TextContent(type="text", text=str(e))]
        except Exception as e:
            # Handle other errors
            raise RuntimeError(f"Error fetching production location details: {str(e)}")
        
    elif name == "create_production_location":
        try:
            # Validate and prepare location data
            location_data = {k: v for k, v in arguments.items() if v is not None}
            
            # Validate required fields
            if not location_data.get('name'):
                raise ValueError("Location name is required")
            if not location_data.get('country'):
                raise ValueError("Country is required")
            
            # Submit the location
            data = await app.create_production_location(location_data)
            
            # The API returns a moderation event, so we'll format it
            formatted_response = {
                "moderation_id": data.get('moderation_id'),
                "status": "Pending moderation"
            }
            
            return [TextContent(type="text", text=json.dumps(formatted_response, indent=2))]
        except Exception as e:
            logger.error(f"Error creating production location: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]
        
    elif name == "moderate_production_location":
        try:
            moderation_id = arguments.get('moderation_id')
            if not moderation_id:
                raise ValueError("Moderation ID is required")
            
            data = await app.moderate_production_location(moderation_id)
            
            formatted_response = {
                "os_id": data.get('os_id'),
                "status": "Location created from moderation event"
            }
            
            return [TextContent(type="text", text=json.dumps(formatted_response, indent=2))]
        except Exception as e:
            logger.error(f"Error moderating production location: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    elif name == "contribute_to_production_location":
        try:
            # Extract OS ID (required)
            os_id = arguments.get('os_id')
            if not os_id:
                raise ValueError("Production location OS ID is required")
            
            # Prepare contribution data (removing OS ID)
            contribution_data = {k: v for k, v in arguments.items() if k != 'os_id' and v is not None}
            
            # Submit the contribution
            data = await app.contribute_to_production_location(os_id, contribution_data)
            
            formatted_response = {
                "moderation_id": data.get('moderation_id'),
                "status": "Contribution submitted for moderation"
            }
            
            return [TextContent(type="text", text=json.dumps(formatted_response, indent=2))]
        except Exception as e:
            logger.error(f"Error contributing to production location: {e}")
            return [TextContent(type="text", text=f"Error: {str(e)}")]
    
    else:
        raise ValueError(f"Unknown tool: {name}")

async def main():
    """Async main entry point"""
    logger.debug("Starting stdio_server")
    try:
        async with stdio_server() as (read_stream, write_stream):
            logger.debug("stdio_server initialized and awaiting input")
            
            try:
                async for message in read_stream:
                    logger.debug(f"Parsed message received: {message}")
                    logger.debug(f"Type hierarchy for message: {type(message).mro()}")

                    root = message.root if hasattr(message, "root") else None
                    
                    if isinstance(root, JSONRPCRequest):
                        logger.debug(f"Handling JSONRPCRequest: {root}")
                        
                        if root.method == "initialize":
                            logger.debug("Initialization method received. Preparing response...")
                            response = JSONRPCResponse(
                                jsonrpc="2.0",
                                id=root.id,
                                result={
                                    "protocolVersion": "2024-11-05",
                                    "capabilities": {
                                        "tools": {
                                            "search_facilities": {
                                                "description": "Search for production location by query in Open Supply Hub.",
                                                "command": "search_facilities"
                                            }
                                        },
                                        "resources": {},  # Should be an object
                                        "prompts": {
                                            "example_prompt": {
                                                "description": "An example prompt",
                                                "options": ["option1", "option2"]
                                            }
                                        }
                                    },
                                    "serverInfo": {"name": "opensupplyhub-server", "version": "0.1.0"},
                                },
                            )
                            await write_stream.send(response)
                            logger.debug("Initialization response sent.")
                            app._initialized = True
                            
                        elif root.method == "tools/list":
                            logger.debug("Handling tools/list method")
                            tools = await list_tools()
                            response = JSONRPCResponse(
                                jsonrpc="2.0",
                                id=root.id,
                                result={"tools": [tool.model_dump() for tool in tools]}
                            )
                            await write_stream.send(response)
                            
                        elif root.method == "tools/call":
                            logger.debug("Handling tools/call method")
                            try:
                                result = await call_tool(
                                    root.params["name"],
                                    root.params.get("arguments", {})
                                )
                                response = JSONRPCResponse(
                                    jsonrpc="2.0",
                                    id=root.id,
                                    result={"content": [content.model_dump() for content in result]}
                                )
                                await write_stream.send(response)
                            except Exception as e:
                                error_response = JSONRPCError(
                                    jsonrpc="2.0",
                                    id=root.id,
                                    error={"code": -32603, "message": str(e)}
                                )
                                await write_stream.send(error_response)
                    
            except Exception as e:
                logger.error(f"Error reading input: {e}", exc_info=True)
                raise
            
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
        raise

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
