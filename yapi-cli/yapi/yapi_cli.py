"""CLI-Anything harness for YApi.

Entry point: yapi-cli
"""

import cmd
import importlib.resources as _pkg_resources
import json
import os
import shlex
import sys
from pathlib import Path
from urllib.parse import urlparse

import click
import requests

from .utils.yapi_backend import YApiBackend

__version__ = "0.1.0"

_REPO_SKILL_PATH = Path(__file__).resolve().parents[2] / "skills" / "SKILL.md"
try:
    if _REPO_SKILL_PATH.exists():
        _SKILL_PATH = str(_REPO_SKILL_PATH)
    else:
        _SKILL_PATH = "skills/SKILL.md"
except Exception:
    _SKILL_PATH = "skills/SKILL.md"


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


@click.group(invoke_without_command=True)
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
@click.version_option(version=__version__, prog_name="yapi-cli")
@click.pass_context
def cli(ctx: click.Context, base_url, token, use_json):
    """yapi-cli — query and manage YApi interfaces from the command line.

    Run without a subcommand to enter the interactive REPL.
    """
    ctx.ensure_object(dict)
    ctx.obj["base_url"] = base_url
    ctx.obj["token"] = token
    ctx.obj["use_json"] = use_json

    if ctx.invoked_subcommand is None:
        _run_repl(ctx.obj)


# ---------------------------------------------------------------------------
# `api` command group
# ---------------------------------------------------------------------------


@cli.group()
def api():
    """Commands for working with YApi interfaces (APIs)."""


@api.command("search")
@click.argument("query")
@click.option("--project", "project_id", default=None, help="Limit search to this project ID.")
@click.option("--url", "yapi_url", default=None, help="YApi interface URL. Project ID will be parsed automatically.")
@click.option("--path", "api_path", default=None, help="Optional path filter, e.g. /user/login.")
@click.option("--page", default=1, show_default=True, help="Page number.")
@click.option("--limit", default=20, show_default=True, help="Max results per project.")
@click.pass_context
def api_search(ctx: click.Context, query: str, project_id, yapi_url, api_path, page: int, limit: int):
    """Search APIs by keyword QUERY across discovered projects (or a specific one)."""
    backend = _backend(ctx)

    if not project_id and yapi_url:
        parsed_project_id, _ = _parse_ids_from_yapi_url(yapi_url)
        if not parsed_project_id:
            raise click.ClickException("Failed to parse project ID from --url.")
        project_id = parsed_project_id

    if project_id:
        project_ids = [project_id]
    else:
        project_ids = backend.configured_project_ids()
        if not project_ids:
            raise click.ClickException(
                "No accessible projects discovered from Cookie. "
                "Use --project to specify one, or refresh YAPI_TOKEN Cookie."
            )

    results = []
    for pid in project_ids:
        try:
            data = backend.search_apis(pid, keyword=query, path=api_path, page=page, limit=limit)
            items = data.get("list", []) if isinstance(data, dict) else data
            for item in items:
                item.setdefault("_project_id", pid)
            results.extend(items)
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


@api.command("get")
@click.argument("project_id", required=False)
@click.argument("api_id", required=False)
@click.option("--url", "yapi_url", default=None, help="YApi interface URL, e.g. /project/{pid}/interface/api/{api_id}.")
@click.pass_context
def api_get(ctx: click.Context, project_id: str | None, api_id: str | None, yapi_url: str | None):
    """Get full details for API_ID in PROJECT_ID."""
    if yapi_url:
        parsed_project_id, parsed_api_id = _parse_ids_from_yapi_url(yapi_url)
        if parsed_project_id:
            project_id = project_id or parsed_project_id
        if parsed_api_id:
            api_id = api_id or parsed_api_id

    if not project_id or not api_id:
        raise click.ClickException("Provide PROJECT_ID/API_ID or pass --url with a valid YApi interface URL.")

    backend = _backend(ctx)
    try:
        data = backend.get_api(project_id, api_id)
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

    _out(ctx, data)


@api.command("save")
@click.option("--project", "project_id", required=True, help="Project ID.")
@click.option("--cat-id", required=True, help="Category ID.")
@click.option("--id", "api_id", default=None, help="API ID (omit to create new).")
@click.option("--title", required=True, help="API title.")
@click.option("--path", "api_path", required=True, help="API path, e.g. /user/login.")
@click.option(
    "--method",
    required=True,
    type=click.Choice(["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"], case_sensitive=False),
    help="HTTP method.",
)
@click.option("--desc", default="", help="API description.")
@click.option("--req-body", default=None, help="Request body schema (JSON string).")
@click.option("--res-body", default=None, help="Response body schema (JSON string).")
@click.pass_context
def api_save(ctx: click.Context, project_id, cat_id, api_id, title, api_path, method, desc, req_body, res_body):
    """Create or update a YApi interface."""
    params: dict = {
        "project_id": project_id,
        "catid": cat_id,
        "title": title,
        "path": api_path,
        "method": method.upper(),
        "desc": desc,
        "status": "done",
    }
    if api_id:
        params["id"] = api_id
    if req_body:
        try:
            json.loads(req_body)  # validate JSON
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"--req-body must be a valid JSON string: {exc}")
        params["req_body_other"] = req_body
        params["req_body_type"] = "json"
    if res_body:
        try:
            json.loads(res_body)  # validate JSON
        except json.JSONDecodeError as exc:
            raise click.ClickException(f"--res-body must be a valid JSON string: {exc}")
        params["res_body"] = res_body
        params["res_body_type"] = "json"

    backend = _backend(ctx)
    data = backend.save_api(params)
    _out(ctx, data)


# ---------------------------------------------------------------------------
# `project` command group
# ---------------------------------------------------------------------------


@cli.group("project")
def project_group():
    """Commands for working with YApi projects."""


@project_group.command("list")
@click.pass_context
def project_list(ctx: click.Context):
    """List all projects accessible with current Cookie session."""
    backend = _backend(ctx)
    try:
        projects = backend.discover_projects()
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        raise click.ClickException(str(exc))

    if not projects:
        click.echo("No projects discovered. Refresh YAPI_TOKEN Cookie or specify project ID manually.")
        return

    if _use_json(ctx):
        click.echo(json.dumps(projects, ensure_ascii=False, indent=2))
    else:
        click.echo(f"{'ID':<12} {'Name':<30} {'Description'}")
        click.echo("-" * 70)
        for info in projects:
            click.echo(
                f"{info.get('_id', ''):<12} "
                f"{info.get('name', ''):<30} "
                f"{info.get('desc', '')}"
            )


# ---------------------------------------------------------------------------
# `category` command group
# ---------------------------------------------------------------------------


@cli.group("category")
def category_group():
    """Commands for working with YApi API categories."""


@category_group.command("list")
@click.argument("project_id")
@click.pass_context
def category_list(ctx: click.Context, project_id: str):
    """List categories (and API counts) for PROJECT_ID."""
    backend = _backend(ctx)
    cats = backend.get_category_list(project_id)

    if _use_json(ctx):
        click.echo(json.dumps(cats, ensure_ascii=False, indent=2))
    else:
        if not cats:
            click.echo("No categories found.")
            return
        click.echo(f"{'ID':<10} {'Name':<30} {'API Count'}")
        click.echo("-" * 55)
        for cat in cats:
            click.echo(
                f"{cat.get('_id', ''):<10} "
                f"{cat.get('name', ''):<30} "
                f"{cat.get('total', 0)}"
            )


# ---------------------------------------------------------------------------
# REPL implementation
# ---------------------------------------------------------------------------


class _YApiRepl(cmd.Cmd):
    intro = (
        f"\n  yapi-cli  v{__version__}\n"
        f"  Skill file: {_SKILL_PATH}\n"
        "  Type 'help' for available commands, 'exit' to quit.\n"
    )
    prompt = "yapi> "

    def __init__(self, obj: dict):
        super().__init__()
        self._obj = obj

    def _invoke(self, line: str):
        try:
            tokens = shlex.split(line)
        except ValueError as exc:
            click.echo(f"Parse error: {exc}", err=True)
            return
        if not tokens:
            return
        try:
            # Build a standalone invocation re-using the same obj context.
            ctx = cli.make_context(
                "yapi-cli",
                tokens,
                obj=dict(self._obj),
                standalone_mode=False,
            )
            with ctx:
                cli.invoke(ctx)
        except click.UsageError as exc:
            click.echo(f"Error: {exc}", err=True)
        except click.exceptions.Exit:
            pass
        except SystemExit:
            pass
        except (requests.RequestException, RuntimeError, ValueError) as exc:
            click.echo(f"Error: {exc}", err=True)

    def default(self, line: str):
        self._invoke(line)

    def do_help(self, arg: str):
        if arg:
            self._invoke(f"{arg} --help")
        else:
            self._invoke("--help")

    def do_exit(self, _arg):
        """Exit the REPL."""
        click.echo("Goodbye.")
        return True

    def do_quit(self, arg):
        """Exit the REPL."""
        return self.do_exit(arg)

    def emptyline(self):
        pass


def _run_repl(obj: dict):
    repl = _YApiRepl(obj)
    try:
        repl.cmdloop()
    except KeyboardInterrupt:
        click.echo("\nInterrupted. Goodbye.")
        sys.exit(0)


if __name__ == "__main__":
    cli()
