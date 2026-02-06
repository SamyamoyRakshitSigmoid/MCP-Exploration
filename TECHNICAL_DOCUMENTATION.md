# Sales Analytics MCP Server - Technical Documentation

Complete technical documentation of the codebase, including function-by-function explanations and system flow.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [MCP Server (`mcp_server.py`)](#mcp-server-mcp_serverpy)
3. [MCP Client (`mcp_client.py`)](#mcp-client-mcp_clientpy)
4. [Gemini Client (`gemini_client.py`)](#gemini-client-gemini_clientpy)
5. [Data Flow](#data-flow)
6. [Integration Patterns](#integration-patterns)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     CLIENT LAYER                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │  Claude Desktop  │         │  Gemini Client   │          │
│  │  (External)      │         │  (gemini_client) │          │
│  └────────┬─────────┘         └────────┬─────────┘          │
│           │                            │                    │
│           │                   ┌────────▼─────────┐          │
│           │                   │   MCPClient      │          │
│           │                   │  (mcp_client)    │          │
│           │                   └────────┬─────────┘          │
│           │                            │                    │
└───────────┼────────────────────────────┼────────────────────┘
            │         MCP Protocol       │
            │         (stdio)            │
┌───────────▼────────────────────────────▼────────────────────┐
│                     SERVER LAYER                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│                  ┌──────────────────┐                       │
│                  │   MCP Server     │                       │
│                  │  (mcp_server)    │                       │
│                  └───────┬──────────┘                       │
│                          │                                  │
│          ┌───────────────┼───────────────┐                  │
│          │               │               │                  │
│   ┌──────▼──────┐  ┌─────▼─────┐  ┌──────▼──────┐           │
│   │ load_data() │  │top_n_     │  │forecast_    │           │
│   │             │  │products() │  │sales()      │           │
│   └─────────────┘  └───────────┘  └─────────────┘           │
│                                                             │
└─────────────────────────┬───────────────────────────────────┘
                          │
                  ┌───────▼────────┐
                  │  CSV Data      │
                  │  (sample_sales │
                  │   _data.csv)   │
                  └────────────────┘
```

---

## MCP Server (`mcp_server.py`)

The MCP server provides sales analytics tools via the Model Context Protocol.

### Imports and Setup

```python
import asyncio
import json
from pathlib import Path
from typing import Any

import pandas as pd
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent
```

**Purpose**: Import necessary libraries for:
- Async operations (`asyncio`)
- Data manipulation (`pandas`)
- MCP server framework (`mcp.server`)
- Type hints (`typing`)

### Global Variables

```python
app = Server("sales-analytics-server")
DATA_PATH = Path(__file__).parent / "data" / "sample_sales_data.csv"
```

- `app`: MCP Server instance with name "sales-analytics-server"
- `DATA_PATH`: Absolute path to the CSV data file

---

### Function: `load_data()`

```python
def load_data() -> pd.DataFrame:
    """Load sales data from CSV file"""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_PATH}")
    return pd.read_csv(DATA_PATH)
```

**Purpose**: Load sales data from CSV file

**Returns**: `pd.DataFrame` containing sales data

**Raises**: `FileNotFoundError` if CSV doesn't exist

**Data Schema**:
- `OPERATION_NAME`: String (e.g., "Dallas", "Charlotte")
- `PRODUCT_ID`: Integer
- `PRODUCT_NAME`: String
- `UNITS_SOLD`: Integer
- `CALENDAR_YEAR`: Integer
- `CALENDAR_MONTH`: Integer

**Called by**: `top_n_products()`, `forecast_sales()`

---

### Function: `top_n_products(n, operation)`

```python
def top_n_products(n: int, operation: str) -> dict[str, Any]:
    """
    Get top N products by units sold for a specific operation
    
    Args:
        n: Number of top products to return
        operation: Operation name to filter by
        
    Returns:
        Dictionary with top products data
    """
```

**Purpose**: Find top-selling products for a given operation

**Algorithm**:
1. Load data via `load_data()`
2. Filter by operation name (case-insensitive substring match)
3. Group by `PRODUCT_ID` and `PRODUCT_NAME`
4. Sum `UNITS_SOLD` for each product
5. Sort descending by units sold
6. Take top N products
7. Convert to list of dictionaries

**Parameters**:
- `n` (int): Number of products to return (minimum: 1)
- `operation` (str): Operation name filter (e.g., "Dallas")

**Returns**:
```json
{
  "operation": "Dallas",
  "top_n": 5,
  "products": [
    {
      "PRODUCT_ID": 123,
      "PRODUCT_NAME": "Product Name",
      "UNITS_SOLD": 50000
    }
  ]
}
```

**Error Handling**: Returns error dict if operation not found:
```json
{
  "error": "No data found for operation: XYZ",
  "products": []
}
```

**Example Flow**:
```
Input: n=5, operation="Dallas"
  ↓
Load CSV data
  ↓
Filter: df[df['OPERATION_NAME'].str.lower().contains('dallas')]
  ↓
Group by: ['PRODUCT_ID', 'PRODUCT_NAME']
  ↓
Aggregate: sum('UNITS_SOLD')
  ↓
Sort: descending by UNITS_SOLD
  ↓
Take: top 5 rows
  ↓
Output: JSON with 5 products
```

---

### Function: `forecast_sales(operation, include_history, start_date)`

```python
def forecast_sales(operation: str, include_history: bool = True, start_date: str = None) -> dict[str, Any]:
    """
    Forecast sales for the next 6 months using Prophet
    
    Args:
        operation: Operation name to filter by
        include_history: Whether to include historical data in forecast
        start_date: Optional start date to filter forecast (YYYY-MM-DD format)
        
    Returns:
        Dictionary with forecast data
    """
```

**Purpose**: Generate 6-month sales forecast using Facebook Prophet

**Algorithm**:
1. Import Prophet library (with fallback to fbprophet)
2. Load and filter data by operation
3. Group by year/month and sum units sold
4. Create date column (YYYY-MM-01 format)
5. Prepare Prophet dataframe with columns: `ds` (date), `y` (value)
6. Fit Prophet model on historical data
7. Generate future dates (6 months from last data point)
8. Create forecast dataframe (with/without history)
9. Predict using Prophet model
10. Extract forecast columns: `ds`, `yhat`, `yhat_lower`, `yhat_upper`
11. Filter by `start_date` if provided
12. Convert to JSON-serializable format

**Parameters**:
- `operation` (str): Operation name (e.g., "Charlotte")
- `include_history` (bool, default=True): Include historical data in results
- `start_date` (str, optional): Filter forecasts from this date (format: "YYYY-MM-DD")

**Returns**:
```json
{
  "operation": "Dallas",
  "include_history": false,
  "start_date": "2025-10-01",
  "forecast": [
    {
      "ds": "2025-10-01",
      "yhat": 1512642,
      "yhat_lower": 1243677,
      "yhat_upper": 1811966
    }
  ]
}
```

**Prophet Model Details**:
- **Input**: Time series of monthly sales
- **Output**: Predicted sales with confidence intervals
- **Components**: Trend + Seasonality
- **Confidence**: 80% interval (yhat_lower to yhat_upper)

**Date Filtering Logic**:
```python
if start_date:
    forecast_data = forecast_data[forecast_data['ds'] >= start_date]
```

**Error Handling**:
- Prophet not installed → Returns error message
- No data for operation → Returns error dict
- Invalid start_date → Silently ignored, returns all data

**Example Flow**:
```
Input: operation="Dallas", include_history=False, start_date="2025-10-01"
  ↓
Load and filter data for Dallas
  ↓
Group by month: ['2024-01', '2024-02', ...]
  ↓
Create Prophet dataframe: {ds: date, y: units_sold}
  ↓
Fit Prophet model on historical data
  ↓
Generate future dates: last_date + 6 months
  ↓
Predict: Prophet.predict(future_dates)
  ↓
Extract: ds, yhat, yhat_lower, yhat_upper
  ↓
Filter: ds >= "2025-10-01"
  ↓
Output: JSON with 6 forecast points
```

---

### MCP Tool Registration: `@app.list_tools()`

```python
@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [...]
```

**Purpose**: Register tools with MCP server

**Returns**: List of `Tool` objects with schemas

**Tool 1: top_n_products**
```python
Tool(
    name="top_n_products",
    description="Get top N products by units sold for a specific operation...",
    inputSchema={
        "type": "object",
        "properties": {
            "n": {
                "type": "integer",
                "description": "Number of top products to return",
                "minimum": 1
            },
            "operation": {
                "type": "string",
                "description": "Operation name to filter by (e.g., 'Dallas', 'Charlotte')"
            }
        },
        "required": ["n", "operation"]
    }
)
```

**Tool 2: forecast_sales**
```python
Tool(
    name="forecast_sales",
    description="Forecast sales for the next 6 months using Prophet...",
    inputSchema={
        "type": "object",
        "properties": {
            "operation": {"type": "string", ...},
            "include_history": {"type": "boolean", "default": True},
            "start_date": {"type": "string", "description": "Optional start date..."}
        },
        "required": ["operation"]
    }
)
```

**Called by**: MCP clients during initialization

---

### MCP Tool Execution: `@app.call_tool()`

```python
@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
```

**Purpose**: Execute tool calls from clients

**Parameters**:
- `name` (str): Tool name ("top_n_products" or "forecast_sales")
- `arguments` (dict): Tool arguments

**Returns**: List of `TextContent` with JSON result

**Execution Flow**:
```
Receive: {name: "top_n_products", arguments: {n: 5, operation: "Dallas"}}
  ↓
Validate: Check required parameters
  ↓
Route: if name == "top_n_products"
  ↓
Execute: result = top_n_products(5, "Dallas")
  ↓
Serialize: json.dumps(result, indent=2)
  ↓
Wrap: TextContent(type="text", text=json_string)
  ↓
Return: [TextContent(...)]
```

**Error Handling**:
```python
try:
    # Execute tool
except Exception as e:
    return [TextContent(text=json.dumps({"error": str(e)}))]
```

---

### Server Entry Points

#### `main()`
```python
def main():
    """Run the MCP server"""
    asyncio.run(run_server())
```

**Purpose**: Synchronous entry point for the server

**Called by**: `if __name__ == "__main__"`

#### `run_server()`
```python
async def run_server():
    """Async server runner"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())
```

**Purpose**: Start MCP server with stdio transport

**Transport**: stdio (standard input/output)

**Lifecycle**:
1. Create stdio streams (read/write)
2. Initialize server with streams
3. Run event loop
4. Handle tool calls
5. Cleanup on exit

---

## MCP Client (`mcp_client.py`)

Reusable client for connecting to the MCP server and calling tools.

### Class: `MCPClient`

```python
class MCPClient:
    """Reusable MCP client for interacting with the sales analytics server"""
```

**Purpose**: Provide a clean API for MCP server interaction

**Attributes**:
- `server_params`: `StdioServerParameters` - Server connection config
- `session`: `ClientSession` - Active MCP session
- `client_context`: Async context manager for stdio client
- `session_context`: Async context manager for session
- `mcp_tools`: List of available tools (populated after connect)

---

### Method: `__init__(server_command, server_args)`

```python
def __init__(self, server_command: str = "python", server_args: List[str] = None):
    """
    Initialize MCP client
    
    Args:
        server_command: Command to run the server (default: "python")
        server_args: Arguments for the server command (default: ["mcp_server.py"])
    """
```

**Purpose**: Configure server connection parameters

**Default Configuration**:
```python
StdioServerParameters(
    command="python",
    args=["mcp_server.py"],
    env=None
)
```

**Example Usage**:
```python
# Default
client = MCPClient()

# Custom
client = MCPClient(
    server_command="/path/to/python",
    server_args=["custom_server.py"]
)
```

---

### Method: `connect()`

```python
async def connect(self) -> ClientSession:
    """Connect to the MCP server and return the session"""
```

**Purpose**: Establish connection to MCP server

**Flow**:
```
1. Create stdio_client context manager
   ↓
2. Enter context: get read/write streams
   ↓
3. Create ClientSession with streams
   ↓
4. Enter session context
   ↓
5. Initialize session (handshake with server)
   ↓
6. List and store available tools
   ↓
7. Return active session
```

**Returns**: `ClientSession` object

**Side Effects**:
- Sets `self.client_context`
- Sets `self.session_context`
- Sets `self.session`
- Sets `self.mcp_tools` (list of available tools)

**Example**:
```python
client = MCPClient()
session = await client.connect()
# Now ready to call tools
```

---

### Method: `disconnect()`

```python
async def disconnect(self):
    """Disconnect from the MCP server"""
```

**Purpose**: Clean up connection resources

**Flow**:
```
1. Exit session context (__aexit__)
   ↓
2. Exit stdio client context (__aexit__)
   ↓
3. Close streams and terminate server process
```

**Example**:
```python
try:
    await client.connect()
    # ... use client ...
finally:
    await client.disconnect()
```

---

### Method: `list_tools()`

```python
async def list_tools(self) -> List[Any]:
    """List all available tools from the server"""
```

**Purpose**: Get list of available tools

**Returns**: List of tool objects with schemas

**Raises**: `RuntimeError` if not connected

**Example**:
```python
tools = await client.list_tools()
for tool in tools:
    print(f"{tool.name}: {tool.description}")
```

---

### Method: `call_tool(tool_name, arguments)`

```python
async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
    """
    Call a tool on the server
    
    Args:
        tool_name: Name of the tool to call
        arguments: Dictionary of arguments for the tool
        
    Returns:
        Tool response
    """
```

**Purpose**: Execute a tool on the server

**Parameters**:
- `tool_name` (str): "top_n_products" or "forecast_sales"
- `arguments` (dict): Tool-specific parameters

**Returns**: Tool result object with `content` attribute

**Example**:
```python
result = await client.call_tool(
    "top_n_products",
    {"n": 5, "operation": "Dallas"}
)
json_data = result.content[0].text
```

---

### Method: `interactive_mode()`

```python
async def interactive_mode(self):
    """Run interactive mode for manual testing"""
```

**Purpose**: Provide CLI for testing tools

**Features**:
- List available tools
- Call tools with JSON arguments
- Interactive REPL

**Commands**:
- `list` - Show all tools
- `call <tool_name> <json_args>` - Execute tool
- `quit` - Exit

**Example Session**:
```
>>> list
🔧 top_n_products
   Get top N products...

>>> call top_n_products {"n": 5, "operation": "Dallas"}
✅ Result:
{...}

>>> quit
```

---

### Function: `run_tests()`

```python
async def run_tests():
    """Run predefined tests (backward compatibility)"""
```

**Purpose**: Execute automated test suite

**Tests**:
1. List all tools
2. Top 5 products in Dallas
3. Top 3 products in Charlotte
4. Forecast Dallas (no history)
5. Forecast Charlotte (with history)

**Usage**: Default mode when running `python mcp_client.py`

---

### Function: `main()`

```python
def main():
    """Entry point for the client"""
```

**Purpose**: CLI entry point with argument parsing

**Command-line Options**:
- (no args) - Run tests
- `-i`, `--interactive` - Interactive mode
- `-l`, `--list-tools` - List tools only
- `-h`, `--help` - Show help

**Example**:
```bash
python mcp_client.py              # Run tests
python mcp_client.py -i           # Interactive
python mcp_client.py --list-tools # List tools
```

---

## Gemini Client (`gemini_client.py`)

Integrates Google Gemini AI with the MCP server for natural language queries.

### Class: `GeminiAgent`

```python
class GeminiAgent:
    """Gemini agent with MCP tool integration."""
```

**Purpose**: Bridge between Gemini AI and MCP tools

**Attributes**:
- `api_key`: Gemini API key
- `model_name`: Gemini model (e.g., "gemini-2.0-flash-exp")
- `mcp_client`: Connected `MCPClient` instance
- `client`: Gemini API client
- `function_declarations`: Gemini-formatted tool schemas

---

### Method: `__init__(api_key, model_name, mcp_client)`

```python
def __init__(self, api_key: str, model_name: str, mcp_client: MCPClient):
    """
    Initialize Gemini agent
    
    Args:
        api_key: Gemini API key
        model_name: Gemini model name
        mcp_client: Connected MCP client
    """
```

**Purpose**: Initialize Gemini with MCP tools

**Flow**:
```
1. Store configuration
   ↓
2. Create Gemini client with API key
   ↓
3. Get MCP tools from client
   ↓
4. Convert to Gemini function declarations
   ↓
5. Store function declarations for chat
```

**Example**:
```python
mcp_client = MCPClient()
await mcp_client.connect()

agent = GeminiAgent(
    api_key="...",
    model_name="gemini-2.0-flash-exp",
    mcp_client=mcp_client
)
```

---

### Method: `_convert_tools_to_gemini()`

```python
def _convert_tools_to_gemini(self) -> list[types.FunctionDeclaration]:
    """Convert MCP tool schemas to Gemini function declarations."""
```

**Purpose**: Transform MCP tool schemas to Gemini format

**Conversion Process**:

**MCP Schema**:
```json
{
  "name": "top_n_products",
  "description": "Get top N products...",
  "inputSchema": {
    "type": "object",
    "properties": {
      "n": {"type": "integer", "description": "..."},
      "operation": {"type": "string", "description": "..."}
    },
    "required": ["n", "operation"]
  }
}
```

**Gemini Function Declaration**:
```python
types.FunctionDeclaration(
    name="top_n_products",
    description="Get top N products...",
    parameters=types.Schema(
        type=types.Type.OBJECT,
        properties={
            "n": types.Schema(
                type=types.Type.INTEGER,
                description="..."
            ),
            "operation": types.Schema(
                type=types.Type.STRING,
                description="..."
            )
        },
        required=["n", "operation"]
    )
)
```

**Type Mapping**:
- `"string"` → `types.Type.STRING`
- `"integer"` → `types.Type.INTEGER`
- `"boolean"` → `types.Type.BOOLEAN`
- `"object"` → `types.Type.OBJECT`

---

### Method: `send_message(message)`

```python
async def send_message(self, message: str) -> str:
    """
    Send a message to Gemini and handle tool calls
    
    Args:
        message: User message
        
    Returns:
        Gemini's response
    """
```

**Purpose**: Process user query with Gemini and execute tools

**Flow**:
```
1. User sends message
   ↓
2. Create Gemini chat with tools
   ↓
3. Send message to Gemini
   ↓
4. Check response for function calls
   ↓
5. If function call detected:
   a. Extract function name and arguments
   b. Call MCP tool via mcp_client
   c. Get result
   d. Send result back to Gemini with context
   e. Get Gemini's interpretation
   ↓
6. Return final text response
```

**Function Call Handling**:
```python
while response.candidates[0].content.parts:
    part = response.candidates[0].content.parts[0]
    
    if hasattr(part, 'function_call') and part.function_call:
        # Extract function call
        function_call = part.function_call
        
        # Execute via MCP
        result = await self.mcp_client.call_tool(
            function_call.name,
            dict(function_call.args)
        )
        
        # Send result back to Gemini
        response = chat.send_message(
            f"Here is the data from {function_call.name}:\n{result}\n..."
        )
    else:
        break  # No more function calls
```

**Date Context for Forecasts**:
```python
if function_call.name == "forecast_sales":
    context_message = f"""IMPORTANT CONTEXT:
- Current date: {datetime.now().strftime('%B %d, %Y')} (Year: 2026)
- These are FUTURE sales forecasts
- Forecast period: {first_date} to {last_date}
- Pay attention to the YEARS in the dates

{result_text}

Please format this data nicely for the user."""
```

**Example Interaction**:
```
User: "What are the top 5 products in Dallas?"
  ↓
Gemini: [function_call: top_n_products(n=5, operation="Dallas")]
  ↓
MCP Tool: Returns JSON with 5 products
  ↓
Gemini: "Here are the top 5 products in Dallas:
1. Product A - 50,000 units
2. Product B - 45,000 units
..."
```

---

### Function: `main()`

```python
async def main():
    """Main entry point for Gemini agent."""
```

**Purpose**: CLI entry point for Gemini client

**Flow**:
```
1. Load .env file
   ↓
2. Get configuration (API key, model, server path)
   ↓
3. Validate API key exists
   ↓
4. Create and connect MCP client
   ↓
5. Create Gemini agent
   ↓
6. Start conversation loop
   ↓
7. Handle user input and responses
   ↓
8. Cleanup on exit
```

**Configuration**:
```python
api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL")
server_path = os.getenv("MCP_SERVER_PATH", "mcp_server.py")
```

**Conversation Loop**:
```python
while True:
    user_input = input("You: ").strip()
    
    if user_input.lower() in ['quit', 'exit', 'q']:
        break
    
    await agent.send_message(user_input)
```

---

## Data Flow

### 1. Claude Desktop Integration

```
User Query (Claude UI)
  ↓
Claude Desktop reads config:
  ~/.config/Claude/claude_desktop_config.json
  ↓
Spawns MCP server process:
  /path/to/uv run python mcp_server.py
  ↓
Establishes stdio connection
  ↓
Claude sends tool call:
  {name: "forecast_sales", args: {operation: "Dallas"}}
  ↓
MCP Server executes:
  forecast_sales("Dallas", True, None)
  ↓
Returns JSON result via stdio
  ↓
Claude interprets and formats response
  ↓
User sees natural language answer
```

### 2. Gemini Client Integration

```
User Query (Terminal)
  "What are the top 5 products in Dallas?"
  ↓
gemini_client.py receives input
  ↓
GeminiAgent.send_message(query)
  ↓
Gemini AI processes query with tool schemas
  ↓
Gemini decides to call: top_n_products(n=5, operation="Dallas")
  ↓
GeminiAgent extracts function call
  ↓
MCPClient.call_tool("top_n_products", {n: 5, operation: "Dallas"})
  ↓
MCP Server (via stdio):
  1. Receives tool call
  2. Executes top_n_products(5, "Dallas")
  3. Returns JSON result
  ↓
MCPClient returns result to GeminiAgent
  ↓
GeminiAgent sends result back to Gemini:
  "Here is the data from top_n_products: {...}"
  ↓
Gemini formats natural language response:
  "The top 5 products in Dallas are:
   1. Product A - 50,000 units
   2. Product B - 45,000 units
   ..."
  ↓
User sees formatted answer
```

### 3. Direct MCP Client Testing

```
python mcp_client.py
  ↓
MCPClient.__init__()
  ↓
MCPClient.connect()
  ↓
Spawns server: python mcp_server.py
  ↓
Establishes stdio connection
  ↓
Initializes session
  ↓
Lists available tools
  ↓
run_tests() executes:
  1. call_tool("top_n_products", {n: 5, operation: "Dallas"})
  2. call_tool("top_n_products", {n: 3, operation: "Charlotte"})
  3. call_tool("forecast_sales", {operation: "Dallas", include_history: False})
  4. call_tool("forecast_sales", {operation: "Charlotte", include_history: True})
  ↓
Prints results to console
  ↓
MCPClient.disconnect()
```

---

## Integration Patterns

### Pattern 1: Claude Desktop (External Client)

**Configuration File**: `~/.config/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "sales-analytics": {
      "command": "/Users/user/.local/bin/uv",
      "args": ["run", "python", "mcp_server.py"],
      "cwd": "/path/to/MCP-Exploration"
    }
  }
}
```

**Lifecycle**:
1. Claude Desktop starts
2. Reads config file
3. Spawns MCP server process for each configured server
4. Maintains persistent stdio connection
5. User queries trigger tool calls
6. Results integrated into conversation

**Advantages**:
- Persistent connection
- Integrated UI
- Context-aware conversations
- Built-in date/time awareness

---

### Pattern 2: Gemini Client (Custom Integration)

**Configuration File**: `.env`

```env
GEMINI_API_KEY=your_api_key_here
GEMINI_MODEL=gemini-2.0-flash-exp
MCP_SERVER_PATH=mcp_server.py
```

**Lifecycle**:
1. User runs `python gemini_client.py`
2. Loads environment variables
3. Creates MCPClient and connects to server
4. Creates GeminiAgent with MCP tools
5. Starts conversation loop
6. Each query:
   - Sent to Gemini API
   - Gemini decides tool usage
   - Tools executed via MCP
   - Results formatted by Gemini
7. Cleanup on exit

**Advantages**:
- Programmatic control
- Custom context injection
- Flexible model selection
- Reusable for other projects

---

### Pattern 3: Direct Client (Testing/Automation)

**Usage**: `python mcp_client.py`

**Modes**:
- **Test Mode** (default): Runs predefined tests
- **Interactive Mode** (`-i`): Manual tool testing
- **List Mode** (`-l`): Show available tools

**Lifecycle**:
1. Parse command-line arguments
2. Create MCPClient
3. Connect to server
4. Execute mode-specific logic
5. Disconnect and exit

**Advantages**:
- Quick testing
- Automation-friendly
- No external dependencies
- Direct API access

---

## Error Handling

### Server-Side Errors

**Tool Execution Errors**:
```python
try:
    result = top_n_products(n, operation)
except Exception as e:
    return [TextContent(text=json.dumps({"error": str(e)}))]
```

**Data Not Found**:
```python
if df_temp.empty:
    return {
        "error": f"No data found for operation: {operation}",
        "products": []
    }
```

**Prophet Not Installed**:
```python
try:
    from prophet import Prophet
except ImportError:
    return {"error": "Prophet library not installed..."}
```

### Client-Side Errors

**Connection Errors**:
```python
if not self.session:
    raise RuntimeError("Not connected to server. Call connect() first.")
```

**Tool Call Errors**:
```python
try:
    result = await self.mcp_client.call_tool(name, args)
except Exception as e:
    print(f"❌ Error calling tool: {e}")
```

**Gemini API Errors**:
```python
except Exception as e:
    print(f"\n❌ Error: {e}")
    response = chat.send_message(f"Error calling function: {str(e)}")
```

---

## Performance Considerations

### Data Loading
- CSV loaded on each tool call (no caching)
- **Optimization**: Add caching for production use

### Prophet Model
- Model fitted on each forecast request
- **Typical time**: 1-3 seconds
- **Optimization**: Cache fitted models by operation

### Stdio Communication
- Synchronous request/response
- **Latency**: Minimal for local connections
- **Scalability**: One server per client connection

---

## Security Considerations

### API Keys
- Stored in `.env` file (gitignored)
- Never committed to version control
- Loaded at runtime only

### Data Access
- No authentication on MCP server
- Assumes trusted local environment
- **Production**: Add authentication layer

### Input Validation
- Basic type checking via JSON schema
- No SQL injection risk (uses pandas)
- **Production**: Add stricter validation

---

## Extension Points

### Adding New Tools

1. **Define function** in `mcp_server.py`:
```python
def new_tool(param1: str, param2: int) -> dict:
    # Implementation
    return {"result": "..."}
```

2. **Register tool** in `list_tools()`:
```python
Tool(
    name="new_tool",
    description="...",
    inputSchema={...}
)
```

3. **Add handler** in `call_tool()`:
```python
elif name == "new_tool":
    result = new_tool(arguments.get("param1"), arguments.get("param2"))
```

4. **Test** with client:
```python
result = await client.call_tool("new_tool", {"param1": "...", "param2": 42})
```

### Adding New Clients

1. **Import MCPClient**:
```python
from mcp_client import MCPClient
```

2. **Connect to server**:
```python
client = MCPClient()
await client.connect()
```

3. **Call tools**:
```python
result = await client.call_tool("tool_name", {...})
```

4. **Process results**:
```python
data = json.loads(result.content[0].text)
```

---

## Troubleshooting

### Common Issues

**Issue**: "Prophet library not installed"
- **Solution**: `uv add prophet` or `pip install prophet`

**Issue**: "Data file not found"
- **Solution**: Ensure `data/sample_sales_data.csv` exists

**Issue**: "Not connected to server"
- **Solution**: Call `await client.connect()` before using tools

**Issue**: Gemini shows wrong dates
- **Solution**: Check date context injection in `send_message()`

**Issue**: Claude Desktop can't find `uv`
- **Solution**: Use full path: `/Users/user/.local/bin/uv`

---

## Summary

This codebase implements a **Model Context Protocol (MCP) server** for sales analytics with:

- **2 Tools**: `top_n_products`, `forecast_sales`
- **3 Clients**: Claude Desktop, Gemini AI, Direct Python
- **1 Data Source**: CSV file with sales data
- **1 ML Model**: Facebook Prophet for forecasting

**Key Design Principles**:
1. **Separation of Concerns**: Server, client, and AI agent are independent
2. **Reusability**: MCPClient can be used by any Python application
3. **Extensibility**: Easy to add new tools and clients
4. **Standard Protocol**: Uses MCP for interoperability

**Architecture Benefits**:
- Tools defined once, used by multiple AI models
- Consistent API across different clients
- Easy testing and debugging
- Production-ready with minimal changes
