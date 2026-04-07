---
name: "yapi-cli"
description: "Use when the user needs to query YApi interfaces."
---

# yapi-cli

A CLI tool for querying YApi interfaces from terminal scripts or AI agents.

## Prerequisites

- Python 3.10+
- Access to a running YApi instance
- Valid YApi Cookie auth (`_yapi_token` and `_yapi_uid`)

## Installation

First, determine `SKILL_PATH` — the directory where this skill is installed:
- If a `pyproject.toml` exists in the current working directory and this skill is part of the project, `SKILL_PATH` is the current directory.
- Otherwise, inspect the path of this SKILL.md file itself; its parent directory is `SKILL_PATH`.

```bash
uv sync --project "$SKILL_PATH"
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

**`.env` auto-load:** A `.env` file in the current working directory is loaded automatically. Existing environment variables are never overwritten.

`projectId:token` mapping formats are not supported.

## Usage

```bash
uv run --project "$SKILL_PATH" yapi [OPTIONS] COMMAND [ARGS]...
```

Command snippets below omit the `uv run --project "$SKILL_PATH"` prefix for readability.

### Global options

| Flag | Description |
|---|---|
| `--base-url TEXT` | YApi base URL (overrides `YAPI_BASE_URL`) |
| `--token TEXT` | Full Cookie string (overrides `YAPI_TOKEN`) |
| `--json` / `--no-json` | Output JSON for machine reading |
| `--version` | Show version and exit |

---

## Agent workflow

For an AI agent consuming API docs, the typical two-step pattern is:

**Step 1 — I have a YApi URL:** jump straight to `api get --url … --pure`

```bash
yapi api get --url "http://host/project/251/interface/api/49315" --pure
```

**Step 2 — I only know the path:** search first, then get details

```bash
# Find the API ID by path (client-side filtered)
yapi api list --project 251 --path /user/login

# Then fetch full details with --pure
yapi api get --api_id 12345 --pure
```

**Use `--pure` by default.** It reduces the response to 7 essential fields and strips internal gateway parameters, which significantly reduces noise for LLM consumption.

---

## Commands

### `api get`

Fetch full details for one API. API ID is globally unique — no project ID needed.

```bash
# By API ID
yapi api get --api_id 49325

# Parse from YApi interface URL
yapi api get --url "http://host/project/12/interface/api/345"

# Filter gateway params, keep essential fields only (recommended for agents)
yapi api get --api_id 49325 --pure
```

Options:

| Flag | Description |
|---|---|
| `--api_id TEXT` | API ID |
| `--url TEXT` | YApi interface URL to parse api_id from |
| `--pure` | Filter gateway params and reduce to essential fields only |

**`--pure` output fields:** `path`, `method`, `title`, `req_query`, `req_body_other`, `res_body_type`, `res_body`

**`res_body` format note:** `res_body` is a JSON Schema string (Draft-04). Parse it to read the response structure. The `--pure` mode unwraps the top-level `data` property when present, so you get the payload schema directly.

**`req_body_other` format note:** Also a JSON Schema string, representing the request body when `Content-Type` is `application/json`.

---

### `api list`

List APIs with optional filters. Path filtering is applied client-side after fetching results.

```bash
# List all APIs in a project
yapi api list --project 251

# Filter by path within a specific project
yapi api list --project 251 --path /save

# Filter by path (searches across all accessible projects — slow on large instances)
yapi api list --path /user/login

# Filter by category (requires --project)
yapi api list --cat 6049 --project 251
```

Options:

| Flag | Description |
|---|---|
| `--project TEXT` | Limit to this project ID (auto-discover all if not provided) |
| `--path TEXT` | Filter by API path (substring match, client-side) |
| `--cat TEXT` | Filter by category ID (requires `--project`) |
| `--page INT` | Page number (default: 1) |
| `--limit INT` | Max results per page (default: 20) |

> **Performance note:** Omitting `--project` triggers project auto-discovery, which may be slow on large YApi instances with many projects. Always supply `--project` when you know the project ID.

---

## JSON mode

```bash
# Get a single API as JSON and extract a field
yapi --json api get --api_id 49325 | jq '.path'

# List APIs and display id/path/title
yapi --json api list --project 251 | jq '.[] | {id: ._id, path, title}'

# Search by path and display matches
yapi --json api list --project 251 --path /save | jq '.[] | {id: ._id, path, title}'

# Parse res_body JSON Schema inline
yapi --json api get --api_id 49325 --pure | jq '.res_body | fromjson | .properties'
```
