from mcp.types import Prompt, PromptArgument, JSONRPCError
from .api import fetch_facilities

# Define prompts
async def list_prompts():
    return [
        Prompt(
            name="search_facilities",
            description="Search facilities in Open Supply Hub",
            arguments=[
                PromptArgument(
                    name="query",
                    description="Search query for facility name or other fields",
                    required=True,
                )
            ],
        )
    ]
async def search_facilities_prompt(arguments):
    query = arguments.get("query")
    if not query:
        raise JSONRPCError(code=-32602, message="Missing required argument 'query'.")
    return await fetch_facilities(query)