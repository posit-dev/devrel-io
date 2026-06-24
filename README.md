# DevRel I/O

**Automated collection of developer relations metrics using [velocirepo](https://github.com/jeroenjanssens/velocirepo).**

Track project adoption, engagement, and growth across GitHub, PyPI, CRAN, Plausible, and OpenVSX. Designed for developer relations teams monitoring open source projects.

## Data Sources

- **GitHub Events**: Stars, forks, issues, PRs, comments (with user and timestamp)
- **PyPI**: Daily download counts
- **CRAN**: Daily download counts
- **Plausible**: Pageviews, visitors, visits
- **OpenVSX**: Extension downloads, ratings, reviews

## Prerequisites

- [velocirepo](https://github.com/jeroenjanssens/velocirepo) (`brew install jeroenjanssens/tap/velocirepo`)

## Quick Start

```bash
# 1. Clone and enter the repository
git clone https://github.com/posit-dev/devrel-io.git
cd devrel-io

# 2. Copy and fill in environment variables
cp .env.example .env
# Edit .env with your tokens

# 3. Fetch all metrics
velocirepo fetch

# 4. Query the data
velocirepo query "SELECT source, COUNT(*) FROM metrics GROUP BY source"
```

## Configuration

Projects are defined in `velocirepo.toml`. Each project can have multiple data sources:

```toml
[projects.my-project]
name = "My Project"
description = "A great project"
color = "#FF5733"
tags = ["python"]
website = "https://example.com"
github-events = "owner/repo"
pypi = "package-name"
plausible = "example.com"
```

## Data Structure

Data is stored as JSONL files at `velocirepo/data/<source>/<project-id>/<date>.jsonl`:

```
velocirepo/data/
├── github/          # GitHub events
│   ├── positron/
│   ├── quarto/
│   └── ...
├── pypi/            # PyPI downloads
├── cran/            # CRAN downloads
├── plausible/       # Web analytics
└── openvsx/         # Extension metrics
```

## Automation

GitHub Actions fetches metrics daily at 6am UTC via the `jeroenjanssens/velocirepo` action.

**Required secrets:**
- `GH_TOKEN` — GitHub Personal Access Token (no scopes needed)
- `PLAUSIBLE_TOKEN` — Plausible API key

## License

MIT
