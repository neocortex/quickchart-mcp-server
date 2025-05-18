#!/usr/bin/env python
"""
QuickChart MCP Server (Simplified Version)

This is a simplified implementation of the QuickChart MCP server that takes a more direct approach
to chart generation compared to the main implementation in `server.py`.

Key differences from the main implementation:
- Does not use Pydantic models for input validation, making it lighter weight
- Expects a complete chart.js configuration object directly from the agent
- Performs only minimal validation on the input configuration
- Has a more straightforward API that accepts the raw chart configuration directly
- Uses a simpler approach to URL generation without the QuickChart library dependency

This version is ideal when you need a more lightweight implementation or when you want
the agent to have more direct control over the chart configuration details.
"""
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any

import asyncio
import httpx
from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

load_dotenv()

QUICKCHART_BASE_URL = os.environ.get("QUICKCHART_BASE_URL", "https://quickchart.io/chart")

# Create the MCP server
mcp = FastMCP("quickchart-server-minimal")

async def generate_chart_url(config: Dict[str, Any]) -> str:
    """Generate a URL for the chart based on the configuration."""
    encoded_config = json.dumps(config)
    return f"{QUICKCHART_BASE_URL}?c={encoded_config}"

@mcp.tool()
async def generate_chart(
    config: Dict[str, Any], 
    download: bool = False, 
    output_path: Optional[str] = None
) -> str:
    """
    Generate a chart using QuickChart.
    
    Args:
        config: A complete chart.js configuration object compatible with QuickChart.
               See https://quickchart.io/documentation/ for examples and format details.
               The config MUST have a 'type' field (one of: bar, line, pie, doughnut, radar,
               polarArea, scatter, bubble, radialGauge, speedometer) and a 'data' field
               with at least one 'datasets' subfield. Choose chart type based on your data.
        download: Whether to download the chart image (default: False)
        output_path: Path where the chart image should be saved if downloading.
                    If not provided but download=True, the image will be saved
                    to the current directory.

   Important: Note that the data fields in each dataset is a list of values like: "data": [-33, 26, 29, 89, -41, 70, -84]

    Example config:
    {
        "type": "bar",
        "data": {
            "labels": ["January", "February", "March", "April", "May", "June", "July"],
            "datasets": [
                {
                    "type": "line",
                    "label": "Dataset 1",
                    "borderColor": "rgb(54, 162, 235)",
                    "borderWidth": 2,
                    "fill": false,
                    "data": [-33, 26, 29, 89, -41, 70, -84]
                },
                {
                    "label": "Dataset 2",
                    "backgroundColor": "rgb(255, 99, 132)",
                    "data": [-42, 73, -69, -94, -81, 18, 87],
                    "borderColor": "white",
                    "borderWidth": 2
                },
                {
                    "label": "Dataset 3",
                    "backgroundColor": "rgb(75, 192, 192)",
                    "data": [93, 60, -15, 77, -59, 82, -44]
                }
            ]
        },
        "options": {
            "title": {
                "display": true,
                "text": "My chart"
            }
        }
    }
    
    Returns:
        URL to the generated chart if download=False, otherwise path where the chart was saved
    """
    if not config:
        raise ValueError("Config cannot be empty")
    
    # Minimal validation - just check for basic structure
    if not isinstance(config, dict):
        raise ValueError("Config must be a dictionary")
    
    # Generate URL
    url = await generate_chart_url(config)
    
    # If not downloading, return the URL
    if not download:
        return url
    
    # Generate default output_path if not provided
    if not output_path:
        # Get script directory
        script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
        
        # Generate a filename based on timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        chart_type = config.get("type", "chart")
        output_path = str(script_dir / f"{chart_type}_{timestamp}.png")
        
        print(f"No output path provided, using: {output_path}")
    
    # Check if the output directory exists and is writable
    output_dir = Path(output_path).parent
    
    if not output_dir.exists():
        raise ValueError(f"Output directory does not exist: {output_dir}")
    
    if not os.access(output_dir, os.W_OK):
        raise ValueError(f"Output directory is not writable: {output_dir}")
    
    # Download and save the image
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        if response.status_code != 200:
            raise Exception(f"Failed to fetch chart: HTTP {response.status_code}")
        
        with open(output_path, "wb") as f:
            f.write(response.content)
    
    return output_path

async def main():
    """
    Main entry point for the MCP server.
    Determines which transport to use (stdio or SSE) based on environment variables.
    """
    # Simple transport selection based on environment variable
    transport = os.getenv("TRANSPORT", "stdio")
    
    if transport == 'sse':      
        # Run the MCP server with SSE transport
        await mcp.run_sse_async()
    else:
        # Run the MCP server with stdio transport
        await mcp.run_stdio_async()
        
if __name__ == "__main__":
    # Run the server
    asyncio.run(main())
    # For development run
    # mcp.run(transport="stdio") 
