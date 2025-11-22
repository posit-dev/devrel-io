# Devrel I/O

A Python CLI tool for developer relations workflows.

## Development Setup

This project uses [uv](https://docs.astral.sh/uv/) for Python package management.

### Prerequisites

- Python 3.8 or higher
- uv (install via `curl -LsSf https://astral.sh/uv/install.sh | sh`)

### Getting Started

1. Clone the repository:
```bash
git clone https://github.com/yourusername/devrel-io.git
cd devrel-io
```

2. Install dependencies:
```bash
uv sync
```

3. Run the application:
```bash
uv run devrel-io
```

### Development

To work on the project:

```bash
# Install dependencies
uv sync

# Run the CLI
uv run devrel-io

# Add new dependencies
uv add package-name

# Add dev dependencies
uv add --dev package-name
```
