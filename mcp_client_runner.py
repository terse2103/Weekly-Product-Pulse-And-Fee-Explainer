import os
import json
import asyncio
import sys
from pathlib import Path
from dotenv import load_dotenv

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# Load environment variables (GDOC_ID, GOOGLE_CLIENT_ID, and GOOGLE_CLIENT_SECRET)
load_dotenv()

async def list_and_execute_mcp():
    target_date = "2026-03-22"
    json_path = Path(f"output/combined_pulse_{target_date}.json")
    
    if not json_path.exists():
        print(f"❌ [Error] File '{json_path}' not found. Please run main.py first.")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    # Prepare the formatted block to append
    text_to_append = f"\n──── {data.get('date', target_date)} ────\n```json\n{json.dumps(data, indent=2)}\n```\n"
    doc_id = os.environ.get("GDOC_ID", "1OUoWFkaWMLC_30VRjjotkHZrhJgq96kXM3QxLMA44mo")
    
    print("▶ Starting LOCAL Python Google Docs MCP Server...")
    
    # This invokes our custom local Python MCP server
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["gdocs_mcp_server.py"], 
        env=os.environ.copy()
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                # 1. Initialize the MCP connection
                await session.initialize()
                print("✅ Successfully connected to LOCAL Python MCP Server.")
                
                # 2. Discover available tools
                print("🔍 Fetching available tools from the server...")
                tools_response = await session.list_tools()
                available_tool_names = [tool.name for tool in tools_response.tools]
                print(f"🛠️ Tools found: {available_tool_names}")
                
                # 3. Call our specific tool
                target_tool = "append_to_google_doc"
                if target_tool not in available_tool_names:
                    print(f"❌ Tool '{target_tool}' not found on server.")
                    return
                
                print(f"🚀 Executing tool '{target_tool}' for document ID '{doc_id}'...")
                
                # Note: These arguments match our Python server's 'append_to_google_doc' function signature
                arguments = {
                    "doc_id": doc_id,
                    "text": text_to_append
                }
                
                try:
                    result = await session.call_tool(target_tool, arguments=arguments)
                    print("\n🎉 SUCCESS! Result from MCP Server:")
                    print(result)
                except Exception as eval_err:
                    print(f"\n❌ [Tool Execution Failed] {eval_err}")
                    
    except Exception as e:
        print(f"\n❌ [Connection Failed] {e}")
        print("Check if gdocs_mcp_server.py exists and if .env has valid GOOGLE_CLIENT_ID/SECRET.")

if __name__ == "__main__":
    asyncio.run(list_and_execute_mcp())
