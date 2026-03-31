"""CLI-Anything harness for YApi.

Entry point: cli-anything-yapi
"""

import cmd
import importlib.resources as _pkg_resources
import json
import shlex
import sys

import click
import requests

from cli_anything.yapi.utils.yapi_backend import YApiBackend

__version__ = "0.1.0"

try:
    _SKILL_PATH = str(_pkg_resources.files("cli_anything.yapi") / "skills" / "SKILL.md")
except Exception:
    _SKILL_PATH = "cli_anything/yapi/skills/SKILL.md"


# ---------------------------------------------------------------------------
# Shared context helpers
# ---------------------------------------------------------------------------


def _backend(ctx: click.Context) -> YApiBackend:
    obj = ctx.find_object(dict)
    return YApiBackend(
        base_url=obj.get("base_url"),
        token=obj.get("token"),
    )


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


# ---------------------------------------------------------------------------
# Root group
# ---------------------------------------------------------------------------


@click.group(invoke_without_command=True)
@click.option("--base-url", envvar="YAPI_BASE_URL", default=None, help="YApi base URL.")
@click.option("--token", envvar="YAPI_TOKEN", default=None, help="YApi token string.")
@click.option(
    "--json/--no-json",
    "use_json",
    default=False,
    help="Output JSON for machine reading.",
)
@click.version_option(version=__version__, prog_name="cli-anything-yapi")
@click.pass_context
def cli(ctx: click.Context, base_url, token, use_json):
    """cli-anything-yapi — query and manage YApi interfaces from the command line.

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
@click.option("--limit", default=20, show_default=True, help="Max results per project.")
@click.pass_context
def api_search(ctx: click.Context, query: str, project_id, limit: int):
    """Search APIs by keyword QUERY across all configured projects (or a specific one)."""
    backend = _backend(ctx)

    if project_id:
        project_ids = [project_id]
    else:
        project_ids = backend.configured_project_ids()
        if not project_ids:
            raise click.ClickException(
                "No project IDs found in YAPI_TOKEN. "
                "Use --project to specify one, or set YAPI_TOKEN=pid:token."
            )

    results = []
    for pid in project_ids:
        try:
            data = backend.search_apis(pid, keyword=query, limit=limit)
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
@click.argument("project_id")
@click.argument("api_id")
@click.pass_context
def api_get(ctx: click.Context, project_id: str, api_id: str):
    """Get full details for API_ID in PROJECT_ID."""
    backend = _backend(ctx)
    data = backend.get_api(project_id, api_id)
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
    """List all projects configured in YAPI_TOKEN."""
    backend = _backend(ctx)
    pids = backend.configured_project_ids()
    if not pids:
        click.echo("No projects configured. Set YAPI_TOKEN=projectId:token,... or use --token.")
        return

    if _use_json(ctx):
        rows = []
        for pid in pids:
            try:
                info = backend.get_project_info(pid)
                rows.append(info)
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                rows.append({"project_id": pid, "error": str(exc)})
        click.echo(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        click.echo(f"{'ID':<12} {'Name':<30} {'Description'}")
        click.echo("-" * 70)
        for pid in pids:
            try:
                info = backend.get_project_info(pid)
                click.echo(
                    f"{info.get('_id', pid):<12} "
                    f"{info.get('name', ''):<30} "
                    f"{info.get('desc', '')}"
                )
            except (requests.RequestException, RuntimeError, ValueError) as exc:
                click.echo(f"{pid:<12} [error: {exc}]")


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
        f"\n  cli-anything-yapi  v{__version__}\n"
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
                "cli-anything-yapi",
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
