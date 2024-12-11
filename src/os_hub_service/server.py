import os
import json
import logging
from datetime import datetime, timedelta
from collections.abc import Sequence
from typing import Any

import aiohttp
import anyio
from dotenv import load_dotenv
from mcp.server import Server
from mcp.types import (
    JSONRPCRequest,
    JSONRPCResponse,
    JSONRPCError,
    Tool,
    TextContent,
    Prompt,
    PromptArgument,
    LoggingLevel
)
from mcp.server.stdio import stdio_server

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("os_hub_service")

# API configuration
API_KEY = os.getenv("OPEN_SUPPLY_HUB_API_KEY")
if not API_KEY:
    raise ValueError("OPEN_SUPPLY_HUB_API_KEY environment variable required")

API_BASE_URL = "https://staging.opensupplyhub.org/api/facilities"

class OSHubServer(Server):
    def __init__(self, name: str):
        super().__init__(name)
        self._initialized = False

    async def initialize(self, options) -> dict:
        """Handle server initialization"""
        logger.info("Starting initialization...")
        try:
            # Test API connection
            headers = {"Authorization": f"Token {API_KEY}"}
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{API_BASE_URL}?q=test", headers=headers) as response:
                    if response.status != 200:
                        raise RuntimeError(f"Failed to fetch data: {response.status}")
            
            self._initialized = True
            logger.info("Server initialization complete")
            
            # Return initialization result
            return {
                "protocolVersion": "1.0",
                "capabilities": {
                    "tools": True,
                    "resources": False,
                    "prompts": True
                },
                "serverInfo": {
                    "name": self.name,
                    "version": "1.0.0"
                }
            }
        except Exception as e:
            logger.error(f"Initialization failed: {e}")
            raise

    async def fetch_facilities(self, query: str) -> dict[str, Any]:
        """Fetch facilities data from Open Supply Hub API."""
        if not self._initialized:
            raise RuntimeError("Server is not initialized")
        
        logger.debug(f"Fetching facilities with query: {query}")
        headers = {"Authorization": f"Token {API_KEY}"}
        url = f"{API_BASE_URL}?q={query}"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                logger.debug(f"Received response: {response.status}")
                if response.status != 200:
                    raise RuntimeError(f"Failed to fetch data: {response.status}")
                data = await response.json()
                logger.debug(f"Response JSON: {data}")
                return data

# Initialize the server
app = OSHubServer("os_hub_server")

@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools."""
    return [
        Tool(
            name="search_facilities",
            description="Search for facilities by query in Open Supply Hub.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Query string to search for facilities."
                    }
                },
                "required": ["query"]
            },
        )
    ]

@app.call_tool()
async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
    """Handle tool calls."""
    if name == "search_facilities":
        query = arguments.get("query", "")
        if not query:
            raise ValueError("Missing 'query' in arguments.")
        data = await app.fetch_facilities(query)
        return [TextContent(type="text", text=json.dumps(data, indent=2))]
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
                                    "protocolVersion": "1.0",
                                    "capabilities": {"tools": True, "resources": False, "prompts": True},
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