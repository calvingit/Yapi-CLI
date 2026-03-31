---
name: "yapi-cli"
description: "Query and manage YApi API documentation from the command line"
---

# yapi-cli

A CLI tool for querying and managing YApi interfaces from terminal scripts or AI agents.

## Prerequisites

- Python 3.10+
- Access to a running YApi instance
- Valid YApi Cookie auth (`_yapi_token` and `_yapi_uid`)

## Installation

```bash
uv sync
```

Or install only the CLI entry point:

```bash
uv pip install -e .
```

## Configuration

| Environment variable | Description | Default |
|---|---|---|
| `YAPI_BASE_URL` | Base URL of your YApi instance | `http://localhost:3000` |
| `_yapi_token` | YApi token from Cookie | *(none)* |
| `_yapi_uid` | YApi uid from Cookie | *(none)* |
| `YAPI_TOKEN` | Full Cookie string fallback (must include `_yapi_token` and `_yapi_uid`) | *(none)* |
| `YAPI_TIMEOUT` | HTTP request timeout in seconds | `15` |

Recommended auth setup:

```bash
export YAPI_BASE_URL=https://yapi.example.com
export _yapi_token='xxxxx'
export _yapi_uid='1234'
```

Fallback Cookie string:

```bash
export YAPI_TOKEN='_yapi_token=xxxxx; _yapi_uid=1234; other_cookie=xxx'
```

`projectId:token` mapping formats are not supported.

## Usage

```bash
yapi-cli [OPTIONS] COMMAND [ARGS]...
```

### Global options

| Flag | Description |
|---|---|
| `--base-url TEXT` | YApi base URL (overrides `YAPI_BASE_URL`) |
| `--token TEXT` | Full Cookie string (overrides `YAPI_TOKEN`) |
| `--json` / `--no-json` | Output JSON for machine reading |
| `--version` | Show version and exit |

---

## Command groups

### `api`

#### `api search <query>`

Search APIs by keyword across discovered projects, or limit to one project.

```bash
# Search across all projects accessible by current Cookie
yapi-cli api search login

# Restrict to one project
yapi-cli api search login --project 12

# Parse project from YApi interface URL
yapi-cli api search login --url "http://host/project/12/interface/api/345"

# Add path filter
yapi-cli api search login --project 12 --path /user/login
```

Options:

| Flag | Description |
|---|---|
| `--project TEXT` | Limit search to this project ID |
| `--url TEXT` | Parse project ID from YApi interface URL |
| `--path TEXT` | Optional API path filter |
| `--page INT` | Page number (default: 1) |
| `--limit INT` | Max results per project (default: 20) |

---

#### `api get [project_id] [api_id]`

Fetch full details for one API.

```bash
yapi-cli api get 12 345

# Parse IDs from URL
yapi-cli api get --url "http://host/project/12/interface/api/345"
```

---

#### `api save`

Create a new API or update an existing one.

```bash
# Create
yapi-cli api save \
  --project 12 \
  --cat-id 56 \
  --title "User Login" \
  --path /user/login \
  --method POST

# Update (with --id)
yapi-cli api save \
  --project 12 \
  --cat-id 56 \
  --id 345 \
  --title "User Login v2" \
  --path /v2/user/login \
  --method POST
```

Options:

| Flag | Required | Description |
|---|---|---|
| `--project TEXT` | Yes | Project ID |
| `--cat-id TEXT` | Yes | Category ID |
| `--id TEXT` | No | API ID (omit to create new) |
| `--title TEXT` | Yes | API title |
| `--path TEXT` | Yes | API path |
| `--method TEXT` | Yes | HTTP method |
| `--desc TEXT` | No | API description |
| `--req-body TEXT` | No | Request body schema (JSON string) |
| `--res-body TEXT` | No | Response body schema (JSON string) |

---

### `project`

#### `project list`

List all projects accessible with current Cookie session.

```bash
yapi-cli project list
yapi-cli --json project list
```

---

### `category`

#### `category list <project_id>`

List categories for a project with API counts.

```bash
yapi-cli category list 12
yapi-cli --json category list 12
```

---

## JSON mode

```bash
yapi-cli --json api search login | jq '.[0]'
yapi-cli --json api get 12 345 | jq '.path'
yapi-cli --json category list 12 | jq '.[] | {id: ._id, name}'
```

## Interactive REPL

Run `yapi-cli` without args:

```bash
$ yapi-cli

  yapi-cli  v0.1.0
  Skill file: skills/SKILL.md
  Type 'help' for available commands, 'exit' to quit.
```
