#!/usr/bin/env python3
"""
Generalized MCP Client for Sales Analytics Server
Provides reusable client functionality and interactive testing
"""

import asyncio
import json
import sys
from typing import Any, Dict, List, Optional
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


class MCPClient:
    """Reusable MCP client for interacting with the sales analytics server"""
    
    def __init__(self, server_command: str = "python", server_args: List[str] = None):
        """
        Initialize MCP client
        
        Args:
            server_command: Command to run the server (default: "python")
            server_args: Arguments for the server command (default: ["mcp_server.py"])
        """
        self.server_params = StdioServerParameters(
            command=server_command,
            args=server_args or ["mcp_server.py"],
            env=None
        )
        self.session: Optional[ClientSession] = None
        
    async def connect(self) -> ClientSession:
        """Connect to the MCP server and return the session"""
        self.client_context = stdio_client(self.server_params)
        self.streams = await self.client_context.__aenter__()
        read, write = self.streams
        
        self.session_context = ClientSession(read, write)
        self.session = await self.session_context.__aenter__()
        await self.session.initialize()
        
        # Load and store tools for Gemini agent
        tools_response = await self.session.list_tools()
        self.mcp_tools = tools_response.tools
        
        return self.session
    
    async def disconnect(self):
        """Disconnect from the MCP server"""
        if self.session:
            await self.session_context.__aexit__(None, None, None)
            await self.client_context.__aexit__(None, None, None)
    
    async def list_tools(self) -> List[Any]:
        """List all available tools from the server"""
        if not self.session:
            raise RuntimeError("Not connected to server. Call connect() first.")
        
        tools_response = await self.session.list_tools()
        return tools_response.tools
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a tool on the server
        
        Args:
            tool_name: Name of the tool to call
            arguments: Dictionary of arguments for the tool
            
        Returns:
            Tool response
        """
        if not self.session:
            raise RuntimeError("Not connected to server. Call connect() first.")
        
        result = await self.session.call_tool(tool_name, arguments=arguments)
        return result
    
    async def interactive_mode(self):
        """Run interactive mode for manual testing"""
        print("🚀 MCP Client - Interactive Mode")
        print("=" * 60)
        
        await self.connect()
        print("✅ Connected to MCP Server\n")
        
        # List available tools
        tools = await self.list_tools()
        print("📋 Available Tools:")
        print("-" * 60)
        for i, tool in enumerate(tools, 1):
            print(f"{i}. {tool.name}")
            print(f"   {tool.description}")
        
        print("\n" + "=" * 60)
        print("Commands:")
        print("  list - List all tools")
        print("  call <tool_name> <json_args> - Call a tool")
        print("  quit - Exit")
        print("=" * 60 + "\n")
        
        while True:
            try:
                user_input = input(">>> ").strip()
                
                if not user_input:
                    continue
                    
                if user_input.lower() == "quit":
                    break
                    
                if user_input.lower() == "list":
                    for tool in tools:
                        print(f"\n🔧 {tool.name}")
                        print(f"   Description: {tool.description}")
                        print(f"   Parameters: {json.dumps(tool.inputSchema, indent=6)}")
                    continue
                
                if user_input.startswith("call "):
                    parts = user_input[5:].split(None, 1)
                    if len(parts) < 2:
                        print("❌ Usage: call <tool_name> <json_args>")
                        continue
                    
                    tool_name = parts[0]
                    try:
                        args = json.loads(parts[1])
                        result = await self.call_tool(tool_name, args)
                        print(f"\n✅ Result:\n{result.content[0].text}\n")
                    except json.JSONDecodeError:
                        print("❌ Invalid JSON arguments")
                    except Exception as e:
                        print(f"❌ Error: {e}")
                    continue
                
                print("❌ Unknown command. Use 'list', 'call', or 'quit'")
                
            except KeyboardInterrupt:
                print("\n")
                break
            except EOFError:
                break
        
        await self.disconnect()
        print("\n👋 Disconnected from server")


async def run_tests():
    """Run predefined tests (backward compatibility)"""
    client = MCPClient()
    
    print("🚀 Starting MCP Client...")
    print("=" * 60)
    
    await client.connect()
    print("✅ Connected to MCP Server\n")
    
    # List available tools
    print("📋 Available Tools:")
    print("-" * 60)
    tools = await client.list_tools()
    for tool in tools:
        print(f"\n🔧 {tool.name}")
        print(f"   Description: {tool.description}")
        print(f"   Parameters: {json.dumps(tool.inputSchema, indent=6)}")
    
    print("\n" + "=" * 60)
    print("\n🧪 Testing Tools...\n")
    
    # Test 1: Get top 5 products for Dallas
    print("Test 1: Top 5 products in Dallas operation")
    print("-" * 60)
    result1 = await client.call_tool("top_n_products", {"n": 5, "operation": "Dallas"})
    print(f"Result:\n{result1.content[0].text}\n")
    
    # Test 2: Get top 3 products for Charlotte
    print("Test 2: Top 3 products in Charlotte operation")
    print("-" * 60)
    result2 = await client.call_tool("top_n_products", {"n": 3, "operation": "Charlotte"})
    print(f"Result:\n{result2.content[0].text}\n")
    
    # Test 3: Forecast sales for Dallas
    print("Test 3: Forecast sales for Dallas (next 6 months only)")
    print("-" * 60)
    result3 = await client.call_tool("forecast_sales", {"operation": "Dallas", "include_history": False})
    forecast_data = json.loads(result3.content[0].text)
    
    if "error" in forecast_data:
        print(f"Error: {forecast_data['error']}\n")
    else:
        print(f"Operation: {forecast_data['operation']}")
        print(f"Number of forecast points: {len(forecast_data['forecast'])}\n")
        print("Sample forecast (first 3 months):")
        for item in forecast_data['forecast'][:3]:
            print(f"  {item['ds']}: {item['yhat']:,} units (range: {item['yhat_lower']:,} - {item['yhat_upper']:,})")
        print()
    
    # Test 4: Forecast sales for Charlotte
    print("Test 4: Forecast sales for Charlotte (with historical data)")
    print("-" * 60)
    result4 = await client.call_tool("forecast_sales", {"operation": "Charlotte", "include_history": True})
    forecast_data = json.loads(result4.content[0].text)
    
    if "error" in forecast_data:
        print(f"Error: {forecast_data['error']}\n")
    else:
        print(f"Operation: {forecast_data['operation']}")
        print(f"Total data points (history + forecast): {len(forecast_data['forecast'])}\n")
        print("Last 3 forecast points:")
        for item in forecast_data['forecast'][-3:]:
            print(f"  {item['ds']}: {item['yhat']:,} units (range: {item['yhat_lower']:,} - {item['yhat_upper']:,})")
        print()
    
    print("=" * 60)
    print("✅ All tests completed!")
    
    await client.disconnect()


def main():
    """Entry point for the client"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--interactive" or sys.argv[1] == "-i":
            asyncio.run(MCPClient().interactive_mode())
        elif sys.argv[1] == "--list-tools" or sys.argv[1] == "-l":
            async def list_only():
                client = MCPClient()
                await client.connect()
                tools = await client.list_tools()
                for tool in tools:
                    print(f"{tool.name}: {tool.description}")
                await client.disconnect()
            asyncio.run(list_only())
        elif sys.argv[1] == "--help" or sys.argv[1] == "-h":
            print("MCP Client Usage:")
            print("  python mcp_client.py              - Run predefined tests")
            print("  python mcp_client.py -i           - Interactive mode")
            print("  python mcp_client.py -l           - List tools only")
            print("  python mcp_client.py -h           - Show this help")
        else:
            print(f"Unknown option: {sys.argv[1]}")
            print("Use --help for usage information")
    else:
        # Default: run tests
        asyncio.run(run_tests())


if __name__ == "__main__":
    main()
