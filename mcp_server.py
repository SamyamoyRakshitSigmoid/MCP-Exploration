#!/usr/bin/env python3
"""
MCP Server for Sales Analytics
Provides tools for analyzing sales data and forecasting
"""

import asyncio
import json
from pathlib import Path
from typing import Any

import pandas as pd
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent


# Initialize server
app = Server("sales-analytics-server")

# Path to data file
DATA_PATH = Path(__file__).parent / "data" / "sample_sales_data.csv"


def load_data() -> pd.DataFrame:
    """Load sales data from CSV file"""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Data file not found: {DATA_PATH}")
    return pd.read_csv(DATA_PATH)


def top_n_products(n: int, operation: str) -> dict[str, Any]:
    """
    Get top N products by units sold for a specific operation
    
    Args:
        n: Number of top products to return
        operation: Operation name to filter by
        
    Returns:
        Dictionary with top products data
    """
    df_data = load_data()
    
    # Filter by operation (case-insensitive)
    operation_lower = operation.lower()
    df_temp = df_data[df_data['OPERATION_NAME'].str.lower().str.contains(operation_lower)]
    
    if df_temp.empty:
        return {
            "error": f"No data found for operation: {operation}",
            "products": []
        }
    
    # Group by product and sum units sold
    df_grouped = df_temp.groupby(['PRODUCT_ID', 'PRODUCT_NAME'])['UNITS_SOLD'].sum().reset_index()
    
    # Get top N products
    df_top_n = df_grouped.sort_values("UNITS_SOLD", ascending=False).head(n)
    
    # Convert to list of dictionaries
    products = df_top_n.to_dict('records')
    
    return {
        "operation": operation,
        "top_n": n,
        "products": products
    }


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
    try:
        from prophet import Prophet
    except ImportError:
        try:
            from fbprophet import Prophet
        except ImportError:
            return {
                "error": "Prophet library not installed. Install with: pip install prophet"
            }
    
    df_data = load_data()
    
    # Filter by operation (case-insensitive)
    operation_lower = operation.lower()
    df_temp = df_data[df_data['OPERATION_NAME'].str.lower().str.contains(operation_lower)]
    
    if df_temp.empty:
        return {
            "error": f"No data found for operation: {operation}",
            "forecast": []
        }
    
    # Group by year and month
    df_grouped = df_temp.groupby(['CALENDAR_YEAR', 'CALENDAR_MONTH'])['UNITS_SOLD'].sum().reset_index()
    
    # Create date column
    df_grouped['Date'] = (
        df_grouped['CALENDAR_YEAR'].astype(str)
        + '-'
        + df_grouped['CALENDAR_MONTH'].astype(str).str.zfill(2)
        + '-01'
    )
    df_grouped['Date'] = pd.to_datetime(df_grouped['Date'])
    df_grouped = df_grouped.sort_values('Date')
    
    # Prepare data for Prophet
    input_series = df_grouped.set_index('Date')['UNITS_SOLD']
    
    # Create Prophet dataframe
    df_prophet = input_series.rename("y").to_frame().reset_index()
    df_prophet.columns = ['ds', 'y']
    
    # Fit Prophet model
    m = Prophet()
    m.fit(df_prophet)
    
    # Create future dataframe for next 6 months
    last_date = df_prophet['ds'].max()
    future_end = last_date + pd.DateOffset(months=6)
    future_dates = pd.date_range(start=last_date, end=future_end, freq='MS')
    
    if include_history:
        future = pd.DataFrame({
            'ds': pd.concat([df_prophet['ds'], pd.Series(future_dates)], ignore_index=True).drop_duplicates().sort_values()
        })
    else:
        future = pd.DataFrame({'ds': future_dates})
    
    # Generate forecast
    forecast = m.predict(future)
    
    # Extract relevant columns and convert to records
    forecast_data = forecast[['ds', 'yhat', 'yhat_lower', 'yhat_upper']].copy()
    forecast_data['ds'] = forecast_data['ds'].dt.strftime('%Y-%m-%d')
    forecast_data['yhat'] = forecast_data['yhat'].round(0).astype(int)
    forecast_data['yhat_lower'] = forecast_data['yhat_lower'].round(0).astype(int)
    forecast_data['yhat_upper'] = forecast_data['yhat_upper'].round(0).astype(int)
    
    # Filter by start_date if provided
    if start_date:
        try:
            forecast_data = forecast_data[forecast_data['ds'] >= start_date]
        except Exception as e:
            # If filtering fails, return all data with a warning
            pass
    
    return {
        "operation": operation,
        "include_history": include_history,
        "start_date": start_date,
        "forecast": forecast_data.to_dict('records')
    }


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List available tools"""
    return [
        Tool(
            name="top_n_products",
            description="Get top N products by units sold for a specific operation. Returns product ID, name, and total units sold.",
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
        ),
        Tool(
            name="forecast_sales",
            description="Forecast sales for the next 6 months using Prophet time series model. Returns predicted values with confidence intervals. Can optionally filter results to show forecasts starting from a specific date.",
            inputSchema={
                "type": "object",
                "properties": {
                    "operation": {
                        "type": "string",
                        "description": "Operation name to filter by (e.g., 'Dallas', 'Charlotte')"
                    },
                    "include_history": {
                        "type": "boolean",
                        "description": "Whether to include historical data in the forecast results",
                        "default": True
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Optional start date to filter forecast results (YYYY-MM-DD format, e.g., '2025-10-01'). Only forecasts from this date onwards will be returned."
                    }
                },
                "required": ["operation"]
            }
        )
    ]


@app.call_tool()
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""
    try:
        if name == "top_n_products":
            n = arguments.get("n")
            operation = arguments.get("operation")
            
            if not n or not operation:
                raise ValueError("Both 'n' and 'operation' parameters are required")
            
            result = top_n_products(n, operation)
            
        elif name == "forecast_sales":
            operation = arguments.get("operation")
            include_history = arguments.get("include_history", True)
            start_date = arguments.get("start_date")
            
            if not operation:
                raise ValueError("'operation' parameter is required")
            
            result = forecast_sales(operation, include_history, start_date)
            
        else:
            raise ValueError(f"Unknown tool: {name}")
        
        return [TextContent(
            type="text",
            text=json.dumps(result, indent=2)
        )]
        
    except Exception as e:
        return [TextContent(
            type="text",
            text=json.dumps({"error": str(e)}, indent=2)
        )]


def main():
    """Run the MCP server"""
    asyncio.run(run_server())


async def run_server():
    """Async server runner"""
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            app.create_initialization_options()
        )


if __name__ == "__main__":
    main()
