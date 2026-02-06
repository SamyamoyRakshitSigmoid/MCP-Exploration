# MCP-Exploration
Exploring Model Context Protocol with Sales Analytics Tools

## Overview

This project implements an MCP (Model Context Protocol) server and client for sales analytics. The server provides two tools:

1. **`top_n_products`**: Get top N products by units sold for a specific operation
2. **`forecast_sales`**: Forecast sales for the next 6 months using Prophet

## Project Structure

```
MCP-Exploration/
├── data/
│   └── sample_sales_data.csv      # Sales data
├── mcp_server.py                   # MCP server implementation
├── mcp_client.py                   # MCP client for testing
├── MCP_tools_example.ipynb         # Original tool prototypes
├── requirements.txt                # Python dependencies
├── claude_desktop_config.json      # Example Claude Desktop config
└── README.md                       # This file
```

## Setup

### Prerequisites

Install [uv](https://docs.astral.sh/uv/) if you haven't already:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### Installation

1. **Install dependencies with uv**:
   ```bash
   uv sync
   ```

2. **Verify data file exists**:
   ```bash
   ls data/sample_sales_data.csv
   ```

## Usage

### Test with Python Client

Run the client to test the server locally:

```bash
# Run predefined tests
uv run python mcp_client.py

# List available tools
uv run python mcp_client.py --list-tools

# Interactive mode
uv run python mcp_client.py --interactive
```

### Use with Gemini AI

1. **Create `.env` file** (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

2. **Add your Gemini API key** to `.env`:
   ```env
   GEMINI_API_KEY=your_actual_api_key_here
   GEMINI_MODEL=gemini-2.0-flash-exp
   MCP_SERVER_PATH=/Users/samyamoyrakshit/Documents/MCP/MCP-Exploration/mcp_server.py
   ```

3. **Run Gemini client**:
   ```bash
   uv run python gemini_client.py
   ```

4. **Ask questions**:
   ```
   You: What are the top 5 products in Dallas?
   You: Forecast sales for Charlotte for the next 6 months
   You: Compare top products between Dallas and Charlotte
   ```

This will:
- Connect to the MCP server
- List available tools
- Test both tools with sample data
- Display results

### Use with Claude Desktop

1. **Copy configuration** to Claude Desktop config file:
   ```bash
   # Location: ~/Library/Application Support/Claude/claude_desktop_config.json
   ```

2. **Add the server configuration**:
   ```json
   {
     "mcpServers": {
       "sales-analytics": {
         "command": "/Users/samyamoyrakshit/.local/bin/uv",
         "args": [
           "--directory",
           "/Users/samyamoyrakshit/Documents/MCP/MCP-Exploration",
           "run",
           "python",
           "mcp_server.py"
         ]
       }
     }
   }
   ```
   
   > **Note**: Use the full path to `uv` (find it with `which uv`). Claude Desktop may not have `uv` in its PATH.

3. **Restart Claude Desktop**

4. **Test in Claude**:
   - "What are the top 5 products in Dallas?"
   - "Forecast sales for Charlotte for the next 6 months"

## Tools

### top_n_products

**Parameters**:
- `n` (integer): Number of top products to return
- `operation` (string): Operation name (e.g., "Dallas", "Charlotte")

**Returns**: List of products with PRODUCT_ID, PRODUCT_NAME, and UNITS_SOLD

**Example**:
```python
{
  "n": 5,
  "operation": "Dallas"
}
```

### forecast_sales

**Parameters**:
- `operation` (string): Operation name (e.g., "Dallas", "Charlotte")
- `include_history` (boolean, optional): Include historical data in results (default: true)

**Returns**: Forecast data with dates, predicted values, and confidence intervals

**Example**:
```python
{
  "operation": "Charlotte",
  "include_history": false
}
```

## Data Format

The sales data CSV includes:
- CALENDAR_MONTH, CALENDAR_YEAR
- OPERATION_ID, OPERATION_NAME
- PRODUCT_ID, PRODUCT_NAME
- UNITS_SOLD, SALES_AMOUNT

## Dependencies

Managed via `pyproject.toml` and `uv`:

**Core Dependencies**:
- `mcp` (>=1.0.0): Model Context Protocol SDK
- `pandas` (>=2.0.0): Data manipulation
- `prophet` (>=1.0.0): Time series forecasting
- `google-genai` (>=0.1.0): Google Gemini AI SDK
- `python-dotenv` (>=1.0.0): Environment variable management

**Development Dependencies**:
- `ipython`: Interactive Python shell
- `jupyter`: Jupyter notebooks
