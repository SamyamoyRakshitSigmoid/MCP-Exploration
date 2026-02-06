#!/usr/bin/env python3
"""
Gemini AI Client for MCP Sales Analytics Server
Integrates Google Gemini with MCP tools for interactive sales analytics
"""

import asyncio
import os
import sys
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Import the existing MCPClient
from mcp_client import MCPClient


class GeminiAgent:
    """Gemini agent with MCP tool integration."""
    
    def __init__(self, api_key: str, model_name: str, mcp_client: MCPClient):
        """
        Initialize Gemini agent.
        
        Args:
            api_key: Gemini API key
            model_name: Gemini model name
            mcp_client: Connected MCP client
        """
        self.api_key = api_key
        self.model_name = model_name
        self.mcp_client = mcp_client
        
        # Create Gemini client
        self.client = genai.Client(api_key=api_key)
        
        # Get tools from MCP client and convert to Gemini format
        self.function_declarations = self._convert_tools_to_gemini()
        
        print(f"✓ Initialized Gemini ({model_name}) with {len(self.function_declarations)} tools")
    
    def _convert_tools_to_gemini(self) -> list[types.FunctionDeclaration]:
        """Convert MCP tool schemas to Gemini function declarations."""
        function_declarations = []
        
        # Get tools from the connected MCP client
        tools = self.mcp_client.mcp_tools
        
        for tool in tools:
            # Convert properties
            properties = {}
            for prop_name, prop_schema in tool.inputSchema.get("properties", {}).items():
                prop_type = prop_schema.get("type", "string").upper()
                properties[prop_name] = types.Schema(
                    type=types.Type[prop_type],
                    description=prop_schema.get("description", ""),
                    enum=prop_schema.get("enum") if prop_schema.get("enum") else None
                )
            
            # Create function declaration
            func_decl = types.FunctionDeclaration(
                name=tool.name,
                description=tool.description,
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties=properties,
                    required=tool.inputSchema.get("required", [])
                )
            )
            function_declarations.append(func_decl)
        
        return function_declarations
    
    async def send_message(self, message: str) -> str:
        """
        Send a message to Gemini and handle tool calls.
        
        Args:
            message: User message
            
        Returns:
            Gemini's response
        """
        print(f"\n💬 You: {message}")
        
        # Create chat with tools
        chat = self.client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                tools=[types.Tool(function_declarations=self.function_declarations)],
                temperature=0.7
            )
        )
        
        # Send initial message
        response = chat.send_message(message)
        
        # Handle function calls
        while response.candidates[0].content.parts:
            part = response.candidates[0].content.parts[0]
            
            # Check if it's a function call
            if hasattr(part, 'function_call') and part.function_call:
                function_call = part.function_call
                
                print(f"\n🔧 Gemini calling tool: {function_call.name}")
                print(f"   Arguments: {dict(function_call.args)}")
                
                # Execute the function call via MCP
                try:
                    result = await self.mcp_client.call_tool(
                        function_call.name,
                        dict(function_call.args)
                    )
                    
                    # Extract text from result
                    result_text = result.content[0].text
                    print(f"✓ Tool result received ({len(result_text)} chars)")
                    
                    # Add context about current date for forecast interpretation
                    import json
                    from datetime import datetime
                    
                    # If it's a forecast, add explicit date context
                    if function_call.name == "forecast_sales":
                        try:
                            forecast_data = json.loads(result_text)
                            if "forecast" in forecast_data and forecast_data["forecast"]:
                                first_date = forecast_data["forecast"][0]["ds"]
                                last_date = forecast_data["forecast"][-1]["ds"]
                                
                                # Create very explicit context message
                                context_message = f"""IMPORTANT CONTEXT:
- Current date: {datetime.now().strftime('%B %d, %Y')} (Year: 2026)
- These are FUTURE sales forecasts
- Forecast period: {first_date} to {last_date}
- Pay attention to the YEARS in the dates - they are 2025 and 2026, NOT 2024

Here is the forecast data from the {function_call.name} function:

{result_text}

Please format this data nicely for the user, making sure to use the CORRECT YEARS from the data (2025-2026)."""
                        except:
                            context_message = f"Here is the data from the {function_call.name} function:\n\n{result_text}\n\nPlease format this nicely for the user."
                    else:
                        context_message = f"Here is the data from the {function_call.name} function:\n\n{result_text}\n\nPlease format this nicely for the user."
                    
                    # Send function response back to Gemini
                    response = chat.send_message(context_message)
                except Exception as e:
                    print(f"❌ Error calling tool: {e}")
                    response = chat.send_message(
                        f"Error calling function {function_call.name}: {str(e)}"
                    )
            else:
                # No more function calls, break
                break
        
        # Get final text response
        final_response = response.text if hasattr(response, 'text') else str(response)
        print(f"\n🤖 Gemini: {final_response}")
        
        return final_response


async def main():
    """Main entry point for Gemini agent."""
    # Load environment variables
    load_dotenv()
    
    api_key = os.getenv("GEMINI_API_KEY")
    model_name = os.getenv("GEMINI_MODEL")
    server_path = os.getenv("MCP_SERVER_PATH", "mcp_server.py")
    
    if not api_key:
        print("❌ Error: GEMINI_API_KEY not set in .env file")
        print("\nPlease create a .env file with:")
        print("  GEMINI_API_KEY=your_api_key_here")
        print(f"  GEMINI_MODEL={model_name}")
        sys.exit(1)
    
    # Create and connect MCP client (reusing existing MCPClient)
    print("🚀 Starting Sales Analytics MCP Client...")
    mcp_client = MCPClient(server_command="python", server_args=[server_path])
    
    try:
        await mcp_client.connect()
        
        # Create Gemini agent
        print("\n🤖 Initializing Gemini Agent...")
        agent = GeminiAgent(api_key, model_name, mcp_client)
        
        print("\n" + "="*60)
        print("Sales Analytics MCP Client with Gemini - Ready!")
        print("="*60)
        print("\nYou can now ask questions about sales data.")
        print("Examples:")
        print("  - What are the top 5 products in Dallas?")
        print("  - Show me top 10 products in Charlotte")
        print("  - Forecast sales for Dallas for the next 6 months")
        print("\nType 'quit' or 'exit' to stop.\n")
        
        # Conversation loop
        while True:
            try:
                user_input = input("You: ").strip()
                
                if user_input.lower() in ['quit', 'exit', 'q']:
                    print("\n👋 Goodbye!")
                    break
                
                if not user_input:
                    continue
                
                # Send message to Gemini
                await agent.send_message(user_input)
                
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
    
    finally:
        # Disconnect from MCP server
        await mcp_client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
