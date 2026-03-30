---
name: "cli-anything-yapi"
description: "Query and manage YApi API documentation from the command line"
---

# cli-anything-yapi

A [CLI-Anything](https://github.com/HKUDS/CLI-Anything) harness for [YApi](https://github.com/YMFE/yapi) — query and manage API documentation from the command line or from an AI agent.

## Prerequisites

- Python 3.10 or newer
- Access to a running YApi instance
- A YApi project token (found in **Project → Settings → Token**)

## Installation

```bash
pip install -e ./agent-harness
```

## Configuration

| Environment variable | Description | Default |
|---|---|---|
| `YAPI_BASE_URL` | Base URL of your YApi instance | `http://localhost:3000` |
| `YAPI_TOKEN` | Token string (see format below) | *(none)* |
| `YAPI_TIMEOUT` | HTTP request timeout in seconds | `15` |

### Token format

**Single token** (used for any project):
```
export YAPI_TOKEN=abc123def456
```

**Per-project tokens** (recommended):
```
export YAPI_TOKEN=12:projectAtoken,34:projectBtoken
```
Where `12` and `34` are the numeric YApi project IDs.

## Usage

```
cli-anything-yapi [OPTIONS] COMMAND [ARGS]...
```

### Global options

| Flag | Description |
|---|---|
| `--base-url TEXT` | YApi base URL (overrides `YAPI_BASE_URL`) |
| `--token TEXT` | Token string (overrides `YAPI_TOKEN`) |
| `--json` / `--no-json` | Output JSON for machine reading (default: human-readable) |
| `--version` | Show version and exit |

---

## Command groups

### `api` — Interface commands

#### `api search <query>`

Search for APIs by keyword across all configured projects (or a specific one).

```bash
# Search all configured projects
cli-anything-yapi api search login

# Limit to a specific project
cli-anything-yapi api search login --project 12

# Return up to 50 results
cli-anything-yapi api search user --limit 50

# Machine-readable JSON output
cli-anything-yapi --json api search order
```

Options:

| Flag | Description |
|---|---|
| `--project TEXT` | Limit search to this project ID |
| `--limit INT` | Max results per project (default: 20) |

---

#### `api get <project_id> <api_id>`

Fetch full details for a single API.

```bash
cli-anything-yapi api get 12 345
cli-anything-yapi --json api get 12 345
```

---

#### `api save`

Create a new API or update an existing one.

```bash
# Create a new API
cli-anything-yapi api save \
  --project 12 \
  --cat-id 56 \
  --title "User Login" \
  --path /user/login \
  --method POST \
  --desc "Authenticate a user and return a JWT."

# Update an existing API (provide --id)
cli-anything-yapi api save \
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
| `--path TEXT` | Yes | API path, e.g. `/user/login` |
| `--method TEXT` | Yes | HTTP method (GET, POST, PUT, DELETE, PATCH, …) |
| `--desc TEXT` | No | API description |
| `--req-body TEXT` | No | Request body schema (JSON string) |
| `--res-body TEXT` | No | Response body schema (JSON string) |

---

### `project` — Project commands

#### `project list`

List all projects that are configured in `YAPI_TOKEN`.

```bash
cli-anything-yapi project list
cli-anything-yapi --json project list
```

---

### `category` — Category commands

#### `category list <project_id>`

List all categories for a project along with their API counts.

```bash
cli-anything-yapi category list 12
cli-anything-yapi --json category list 12
```

---

## Machine-readable output (`--json`)

Pass `--json` (before the subcommand) to receive valid JSON on stdout, suitable for piping into `jq` or an AI agent:

```bash
cli-anything-yapi --json api search login | jq '.[0]'
cli-anything-yapi --json api get 12 345 | jq '.path'
cli-anything-yapi --json category list 12 | jq '.[] | {id: ._id, name}'
```

---

## Interactive REPL

Run `cli-anything-yapi` with no arguments to enter the interactive REPL:

```
$ cli-anything-yapi

  cli-anything-yapi  v0.1.0
  Skill file: agent-harness/cli_anything/yapi/skills/SKILL.md
  Type 'help' for available commands, 'exit' to quit.

yapi> api search login
yapi> project list
yapi> category list 12
yapi> exit
```

---

## Common workflows

### Discover what APIs exist in a project

```bash
# 1. List categories
cli-anything-yapi category list 12

# 2. Search for specific functionality
cli-anything-yapi api search payment --project 12

# 3. Inspect a single API in detail
cli-anything-yapi api get 12 789
```

### Create an API from a script

```bash
export YAPI_BASE_URL=https://yapi.mycompany.com
export YAPI_TOKEN=12:mytoken

cli-anything-yapi api save \
  --project 12 \
  --cat-id 56 \
  --title "Create Order" \
  --path /api/v1/orders \
  --method POST \
  --desc "Place a new customer order." \
  --req-body '{"type":"object","properties":{"item_id":{"type":"integer"}}}' \
  --res-body '{"type":"object","properties":{"order_id":{"type":"integer"}}}'
```

### Use with an AI agent (JSON mode)

```bash
# Agent discovers available APIs
APIS=$(cli-anything-yapi --json api search user)

# Agent inspects the first result
FIRST_ID=$(echo "$APIS" | jq -r '.[0]._id')
PROJECT_ID=$(echo "$APIS" | jq -r '.[0].project_id')
cli-anything-yapi --json api get "$PROJECT_ID" "$FIRST_ID"
```
