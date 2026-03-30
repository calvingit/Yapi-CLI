"""YApi HTTP API backend — reads config from environment variables or explicit args."""

import os
from typing import Optional

import requests

_DEFAULT_BASE_URL = "http://localhost:3000"
_DEFAULT_TIMEOUT = int(os.environ.get("YAPI_TIMEOUT", "15"))


def _parse_token_map(token_str: str) -> dict[str, str]:
    """Parse YAPI_TOKEN into {project_id: token}.

    Formats accepted:
      - plain token string (no colon) → stored under key "*"
      - projectId:token,projectId2:token2 → per-project map
    """
    result: dict[str, str] = {}
    if not token_str:
        return result
    for part in token_str.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            pid, tok = part.split(":", 1)
            result[pid.strip()] = tok.strip()
        else:
            result["*"] = part
    return result


class YApiBackend:
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or os.environ.get("YAPI_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        raw_token = token or os.environ.get("YAPI_TOKEN", "")
        self._token_map = _parse_token_map(raw_token)
        self._timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT

    # ------------------------------------------------------------------
    # Token helpers
    # ------------------------------------------------------------------

    def get_token(self, project_id: str) -> str:
        """Return the token for *project_id*, falling back to the wildcard token."""
        tok = self._token_map.get(str(project_id)) or self._token_map.get("*")
        if not tok:
            raise ValueError(
                f"No token configured for project {project_id}. "
                "Set YAPI_TOKEN=projectId:token or pass --token."
            )
        return tok

    def configured_project_ids(self) -> list[str]:
        """Return all explicitly-configured project IDs (excludes the wildcard '*')."""
        return [pid for pid in self._token_map if pid != "*"]

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict) -> dict:
        url = f"{self.base_url}{path}"
        resp = requests.get(url, params=params, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"YApi error {data.get('errcode')}: {data.get('errmsg', 'unknown')}")
        return data

    def _post(self, path: str, json_body: dict, token: str) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json"}
        json_body = dict(json_body)
        json_body.setdefault("token", token)
        resp = requests.post(url, json=json_body, headers=headers, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode", 0) != 0:
            raise RuntimeError(f"YApi error {data.get('errcode')}: {data.get('errmsg', 'unknown')}")
        return data

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_api(self, project_id: str, api_id: str) -> dict:
        """GET /api/interface/get — fetch a single API by ID."""
        token = self.get_token(project_id)
        data = self._get("/api/interface/get", {"id": api_id, "token": token})
        return data.get("data", data)

    def search_apis(
        self,
        project_id: str,
        keyword: Optional[str] = None,
        path: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ) -> dict:
        """GET /api/interface/list — list/search APIs in a project."""
        token = self.get_token(project_id)
        params: dict = {"project_id": project_id, "token": token, "page": page, "limit": limit}
        if keyword:
            params["q"] = keyword
        if path:
            params["path"] = path
        data = self._get("/api/interface/list", params)
        return data.get("data", data)

    def get_project_info(self, project_id: str) -> dict:
        """GET /api/project/get — fetch project metadata."""
        token = self.get_token(project_id)
        data = self._get("/api/project/get", {"id": project_id, "token": token})
        return data.get("data", data)

    def get_category_list(self, project_id: str) -> list:
        """GET /api/interface/getCatMenu — list categories for a project."""
        token = self.get_token(project_id)
        data = self._get("/api/interface/getCatMenu", {"project_id": project_id, "token": token})
        return data.get("data", [])

    def get_category_apis(
        self,
        project_id: str,
        cat_id: str,
        page: int = 1,
        limit: int = 100,
    ) -> list:
        """GET /api/interface/list_cat — list APIs in a category."""
        token = self.get_token(project_id)
        data = self._get(
            "/api/interface/list_cat",
            {"catid": cat_id, "token": token, "page": page, "limit": limit},
        )
        return data.get("data", {}).get("list", [])

    def save_api(self, params: dict) -> dict:
        """POST /api/interface/add or /api/interface/up — create or update an API.

        If *params* contains 'id', the update endpoint is used.
        Caller must include 'project_id' in *params*.
        """
        project_id = str(params.get("project_id", ""))
        if not project_id:
            raise ValueError("'project_id' is required in params for save_api.")
        token = self.get_token(project_id)
        endpoint = "/api/interface/up" if params.get("id") else "/api/interface/add"
        data = self._post(endpoint, params, token)
        return data.get("data", data)
