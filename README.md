# QuickChart MCP Server

An MCP server implementation for [QuickChart.io](https://quickchart.io/), allowing you to generate and download charts directly through Claude Desktop and other MCP clients.

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/quickchart-mcp.git
cd quickchart-mcp
```
## Usage

### Running as a standalone MCP server

```bash
uv run src/server.py
```

### Configuring in Claude Desktop and other MCP clients

Add the following configuration to your Claude Desktop configuration file or equivalent for other MCP clients:

```json
"quickchart": {
  "command": "/path/to/uv",
  "args": [
    "run",
    "--directory",
    "/path/to/quickchart-mcp/src",
    "server.py"
  ]
}
```

Make sure to replace `/path/to/uv` with the actual path to your uv executable and `/path/to/quickchart-mcp/src` with the path to your quickchart-mcp source directory.

## Available Tool

### `generate_chart`

Generates a chart using QuickChart and optionally downloads it.

**Parameters:**

- `config`: Complete chart.js configuration object
- `download`: Whether to download the chart (default: False)
- `output_path`: Path to save the chart image (optional)

**Example usage:**

```json
{
  "type": "bar",
  "data": {
    "labels": ["January", "February", "March"],
    "datasets": [
      {
        "label": "Sales",
        "data": [50, 60, 70],
        "backgroundColor": "rgba(75, 192, 192, 0.2)"
      }
    ]
  }
}
```

See the [QuickChart documentation](https://quickchart.io/documentation/) for more configuration options.

## Requirements

- Python 3.12+
- Dependencies: httpx, mcp, python-dotenv
