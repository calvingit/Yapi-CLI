"""YApi CLI.

Entry point: yapi
"""

import json
import os
from pathlib import Path
from urllib.parse import urlparse

import click
import requests

from yapi_backend import YApiBackend
from formatter import format_api_data

__version__ = "0.1.0"


def _strip_env_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value


def _load_local_dotenv() -> None:
    """Best-effort load of .env in current working directory.

    Existing environment variables are preserved.
    """
    env_path = Path.cwd() / ".env"
    if not env_path.exists() or not env_path.is_file():
        return

    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key:
                continue
            value = _strip_env_quotes(value.strip())
            os.environ.setdefault(key, value)
    except OSError:
        # Ignore local .env read failures and keep CLI behavior predictable.
        return


_load_local_dotenv()


# ---------------------------------------------------------------------------
# Shared context helpers
# ---------------------------------------------------------------------------


def _backend(ctx: click.Context) -> YApiBackend:
    obj = ctx.find_object(dict)
    try:
        return YApiBackend(
            base_url=obj.get("base_url"),
            token=obj.get("token"),
        )
    except ValueError as exc:
        raise click.ClickException(str(exc))


def _use_json(ctx: click.Context) -> bool:
    return ctx.find_object(dict).get("use_json", False)


def _out(ctx: click.Context, data) -> None:
    if _use_json(ctx):
        click.echo(json.dumps(data, ensure_ascii=False, indent=2))
    else:
        if isinstance(data, (dict, list)):
            click.echo(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            click.echo(data)


def _parse_ids_from_yapi_url(url: str) -> tuple[str | None, str | None]:
    """Parse project_id and api_id from YApi interface URL.

    Example:
      http://host/project/908/interface/api/921695 -> ("908", "921695")
    """
    try:
        path_parts = [p for p in urlparse(url).path.split("/") if p]
    except Exception:
        return None, None

    project_id = None
    api_id = None
    for i, part in enumerate(path_parts):
        if part == "project" and i + 1 < len(path_parts):
            project_id = path_parts[i + 1]
        if part == "api" and i + 1 < len(path_parts):
            api_id = path_parts[i + 1]
    return project_id, api_id


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group()
@click.option("--base-url", envvar="YAPI_BASE_URL", default=None, help="YApi base URL.")
@click.option(
    "--token",
    envvar="YAPI_TOKEN",
    default=None,
    help="YApi full Cookie string (optional if env vars _yapi_token and _yapi_uid are set).",
)
@click.option(
    "--json/--no-json",
    "use_json",
    default=False,
    help="Output JSON for machine reading.",
)
@click.version_option(version=__version__, prog_name="yapi")
@click.pass_context
def cli(ctx: click.Context, base_url, token, use_json):
    """yapi — query YApi interfaces from the command line."""
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["token"] = token
    ctx.obj["use_json"] = use_json


# ---------------------------------------------------------------------------
# `api` command group — Query APIs only
# ---------------------------------------------------------------------------


@cli.group()
def api():
    """Commands for querying YApi interfaces."""


@api.command("get")
@click.option(
    "--url", "yapi_url", default=None, help="YApi interface URL to parse api_id from."
)
@click.option("--api_id", default=None, help="Directly specify API ID (e.g., 56290).")
@click.option(
    "--pure",
    is_flag=True,
    default=False,
    help="Filter gateway params and reduce to essential fields only.",
)
@click.pass_context
def api_get(ctx: click.Context, yapi_url: str | None, api_id: str | None, pure: bool):
    """Get a single API interface by ID.

    Use --api_id to specify directly, or --url to parse from YApi URL.
    API ID is globally unique, so project ID is not required.
    Use --pure to strip gateway parameters and keep only essential fields.
    """
    # Parse from URL if provided
    if yapi_url:
        _, parsed_api_id = _parse_ids_from_yapi_url(yapi_url)
        if parsed_api_id:
            api_id = api_id or parsed_api_id

    if not api_id:
        raise click.ClickException(
            "Provide --api_id directly or --url with a valid YApi interface URL."
        )

    backend = _backend(ctx)
    try:
        data = backend.get_api("", api_id)  # project_id not needed for direct API query
    except requests.RequestException as exc:
        raise click.ClickException(f"Network error while fetching API: {exc}")
    except RuntimeError as exc:
        msg = str(exc)
        if "authentication failed" in msg.lower() or "请登录" in msg:
            raise click.ClickException(
                "YApi Cookie authentication failed. "
                "Please refresh YAPI_TOKEN and ensure it includes both _yapi_token and _yapi_uid."
            )
        raise click.ClickException(msg)
    except ValueError as exc:
        raise click.ClickException(str(exc))

    if pure:
        data = format_api_data(data)
    _out(ctx, data)


@api.command("list")
@click.option(
    "--project",
    "project_id",
    default=None,
    help="Limit to this project ID (discover all if not provided).",
)
@click.option(
    "--path", "api_path", default=None, help="Filter by API path (e.g., /user/login)."
)
@click.option(
    "--cat", "cat_id", default=None, help="Filter by category ID (requires --project)."
)
@click.option("--page", default=1, show_default=True, help="Page number.")
@click.option("--limit", default=20, show_default=True, help="Max results per page.")
@click.pass_context
def api_list(
    ctx: click.Context,
    project_id: str | None,
    api_path: str | None,
    cat_id: str | None,
    page: int,
    limit: int,
):
    """List APIs with optional filters.

    Filter by --path (e.g., /save), --cat (category ID, requires --project),
    or --project to limit results to a specific project.
    """
    backend = _backend(ctx)
    results = []

    # If --cat is provided, list APIs in that category
    if cat_id:
        if not project_id:
            raise click.ClickException(
                "--cat requires --project (categories are project-specific). "
                "Example: yapi api list --cat 6049 --project 251"
            )
        try:
            data = backend.get_category_apis(project_id, cat_id, page=page, limit=limit)
            results = data if isinstance(data, list) else []
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            raise click.ClickException(f"Failed to fetch category {cat_id}: {exc}")
    else:
        # Search by path in project(s)
        if project_id:
            project_ids = [project_id]
        else:
            try:
                project_ids = backend.configured_project_ids()
                if not project_ids:
                    raise click.ClickException(
                        "No accessible projects discovered. Use --project to specify one."
                    )
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                raise click.ClickException(f"Failed to discover projects: {exc}")

        # When filtering by path, fetch a larger page to improve recall.
        # YApi server ignores the path param, so filtering happens client-side.
        fetch_limit = 200 if api_path else limit
        for pid in project_ids:
            try:
                data = backend.search_apis(pid, page=page, limit=fetch_limit)
                items = data.get("list", []) if isinstance(data, dict) else data
                if api_path:
                    items = [item for item in items if api_path.lower() in item.get("path", "").lower()]
                for item in items[:limit]:
                    item.setdefault("_project_id", pid)
                results.extend(items[:limit])
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                click.echo(f"[warn] project {pid}: {exc}", err=True)

    if _use_json(ctx):
        click.echo(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        if not results:
            click.echo("No APIs found.")
            return
        click.echo(f"{'ID':<10} {'Project':<10} {'Method':<8} {'Path':<40} {'Title'}")
        click.echo("-" * 90)
        for item in results:
            click.echo(
                f"{item.get('_id', ''):<10} "
                f"{item.get('_project_id', item.get('project_id', '')):<10} "
                f"{item.get('method', ''):<8} "
                f"{item.get('path', ''):<40} "
                f"{item.get('title', '')}"
            )


if __name__ == "__main__":
    cli()
