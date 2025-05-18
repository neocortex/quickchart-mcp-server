#!/usr/bin/env python3
import os
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union, Any, Optional, Literal

import httpx
from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator
from mcp.server.fastmcp import FastMCP
from quickchart import QuickChart

load_dotenv()

# Get base URL from environment variable or use default
QUICKCHART_BASE_URL = os.environ.get('QUICKCHART_BASE_URL', 'https://quickchart.io/chart')

# Define the QuickChart MCP server
mcp = FastMCP("QuickChart")

# Valid chart types
ChartType = Literal[
    'bar', 'line', 'pie', 'doughnut', 'radar',
    'polarArea', 'scatter', 'bubble', 'radialGauge', 'speedometer'
]

# Define data point types for different chart formats
DataPoint = Union[float, int]
ScatterPoint = List[Union[float, int]]  # [x, y] format
BubblePoint = List[Union[float, int]]   # [x, y, r] format


class Dataset(BaseModel):
    """Data model for chart datasets"""
    label: str = ""
    data: List[Union[DataPoint, ScatterPoint, BubblePoint]]
    backgroundColor: Optional[Union[str, List[str]]] = None
    borderColor: Optional[Union[str, List[str]]] = None
    additionalConfig: Optional[Dict[str, Any]] = Field(default_factory=dict)

    model_config = {"extra": "allow"}  # Allow additional fields
    
    @field_validator('data')
    def validate_data_format(cls, v):
        """Validate that data has the correct format"""
        if not v:
            raise ValueError("Data cannot be empty")
            
        # Check that all items are either numbers or lists of numbers
        for item in v:
            if isinstance(item, list):
                if not all(isinstance(x, (int, float)) for x in item):
                    raise ValueError("For scatter/bubble charts, data points must be lists of numbers")
                if not (2 <= len(item) <= 3):
                    raise ValueError("Data points for scatter/bubble charts must be [x,y] or [x,y,r] format")
            elif not isinstance(item, (int, float)):
                raise ValueError("Data must be a list of numbers or a list of coordinate points")
                
        return v


class ChartData(BaseModel):
    """Data model for chart data"""
    labels: List[str] = Field(default_factory=list)
    datasets: List[Dataset]


class ChartOptions(BaseModel):
    """Data model for chart options"""
    title: Optional[Dict[str, Any]] = None
    plugins: Optional[Dict[str, Any]] = None
    
    model_config = {"extra": "allow"}  # Allow additional fields for other options


class ChartConfig(BaseModel):
    """Data model for the complete chart configuration"""
    type: ChartType
    data: ChartData
    options: ChartOptions = Field(default_factory=ChartOptions)
    
    @field_validator('data')
    def validate_chart_data(cls, v, info):
        """Validate chart data based on chart type"""
        values = info.data
        if 'type' not in values:
            return v
            
        chart_type = values['type']
        
        # Special handling for specific chart types
        if chart_type in ["radialGauge", "speedometer"]:
            if not v.datasets or not v.datasets[0].data or len(v.datasets[0].data) == 0:
                raise ValueError(f"{chart_type} requires a single numeric value")
                
        elif chart_type in ["scatter", "bubble"]:
            for dataset in v.datasets:
                if not dataset.data:
                    raise ValueError(f"{chart_type} requires data points")
                
                for item in dataset.data:
                    if not isinstance(item, list):
                        point_format = "[x, y]" if chart_type == "scatter" else "[x, y, r]"
                        raise ValueError(f"{chart_type} requires data points in {point_format} format")
                    
                    min_items = 2
                    max_items = 3 if chart_type == "bubble" else 2
                    if not (min_items <= len(item) <= max_items):
                        point_format = "[x, y]" if chart_type == "scatter" else "[x, y, r]"
                        raise ValueError(f"{chart_type} requires data points in {point_format} format")
        
        # For standard chart types, data should be numbers
        elif chart_type in ["bar", "line", "pie", "doughnut", "radar", "polarArea"]:
            for dataset in v.datasets:
                for item in dataset.data:
                    if isinstance(item, list):
                        raise ValueError(f"{chart_type} requires data to be a list of numbers, not coordinate points")
        
        return v


class ChartInput(BaseModel):
    """Input model for chart generation"""
    type: ChartType
    datasets: List[Dataset]
    labels: Optional[List[str]] = Field(default_factory=list)
    title: Optional[str] = None
    options: Optional[Dict[str, Any]] = Field(default_factory=dict)


def generate_chart_url(config: Dict[str, Any]) -> str:
    """Generate a QuickChart URL from a chart configuration."""
    qc = QuickChart()
    qc.width = 600
    qc.height = 300
    qc.device_pixel_ratio = 2.0
    qc.config = json.dumps(config)
    return qc.get_url()


def create_chart_config(chart_input: ChartInput) -> Dict[str, Any]:
    """Generate a chart configuration directly from a ChartInput model.
    
    Args:
        chart_input: The validated ChartInput model
        
    Returns:
        A dictionary containing the chart configuration
    """
    # Create datasets with additionalConfig fields expanded
    processed_datasets = []
    for dataset in chart_input.datasets:
        # Convert dataset to dict and remove additionalConfig
        dataset_dict = dataset.model_dump(exclude_none=True)
        additional_config = dataset_dict.pop('additionalConfig', {})
        
        # Merge additional config with dataset dict
        dataset_dict.update(additional_config or {})
        processed_datasets.append(dataset_dict)

    # Build config
    config = {
        "type": chart_input.type,
        "data": {
            "labels": chart_input.labels,
            "datasets": processed_datasets
        },
        "options": chart_input.options or {}
    }
    
    # Add title if provided
    if chart_input.title:
        if "title" not in config["options"]:
            config["options"]["title"] = {"display": True, "text": chart_input.title}
    
    # Special handling for specific chart types
    if chart_input.type in ["radialGauge", "speedometer"]:
        if "plugins" not in config["options"]:
            config["options"]["plugins"] = {}
        
        config["options"]["plugins"]["datalabels"] = {
            "display": True,
            "formatter": "(value) => value"
        }
    
    return config


@mcp.tool()
async def generate_chart(
    chart_input: ChartInput, download: bool = False, output_path: Optional[str] = None
) -> str:
    """
    Generate a chart using QuickChart.
    
    Args:
        chart_input: Chart configuration including type, datasets, labels, title, and options
        download: If True, download the chart image and return the saved file path; otherwise return the URL
        output_path: Path where the chart image should be saved if download=True. If not provided,
                    the chart will be saved to the script directory.
        
    Returns:
        The URL of the generated chart if download=False, otherwise the path where the chart was saved
    """
    try:
        # Generate chart config directly from the model
        config = create_chart_config(chart_input)
        
        # Generate URL from config
        url = generate_chart_url(config)
        
        # If not downloading, return the URL
        if not download:
            return url
        
        # Generate default output_path if not provided
        if not output_path:
            # Get script directory
            script_dir = Path(os.path.dirname(os.path.abspath(__file__)))
            
            # Generate a filename based on timestamp
            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            chart_type = chart_input.type
            
            # Add title to filename if available
            filename_parts = [chart_type]
            if chart_input.title:
                # Make the title safe for filesystem use
                safe_title = "".join(c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in chart_input.title)
                safe_title = safe_title.strip().replace(' ', '_')
                filename_parts.append(safe_title)
            
            filename_parts.append(timestamp)
            output_path = str(script_dir / f"{'_'.join(filename_parts)}.png")
            
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
        
    except Exception as e:
        raise ValueError(f"Failed to generate chart: {str(e)}")


if __name__ == "__main__":
    mcp.run() 