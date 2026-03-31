"""YApi HTTP API backend — Cookie authentication only."""

import os
from typing import Optional

import requests

_DEFAULT_BASE_URL = "http://localhost:3000"
_DEFAULT_TIMEOUT = int(os.environ.get("YAPI_TIMEOUT", "15"))


def _is_cookie_auth(raw_auth: str) -> bool:
    """Return True when *raw_auth* looks like a YApi Cookie header value."""
    return "_yapi_token=" in raw_auth and "_yapi_uid=" in raw_auth


def _build_cookie(raw_cookie: str, yapi_token: str, yapi_uid: str) -> str:
    """Build a Cookie string from split vars, or validate a full Cookie string."""
    token_part = yapi_token.strip()
    uid_part = yapi_uid.strip()
    if token_part and uid_part:
        return f"_yapi_token={token_part}; _yapi_uid={uid_part}"

    cookie = raw_cookie.strip()
    if _is_cookie_auth(cookie):
        return cookie

    if cookie:
        raise ValueError(
            "YAPI_TOKEN full Cookie format is required when using YAPI_TOKEN, "
            "or provide split vars _yapi_token and _yapi_uid. "
            "projectId:token format is no longer supported."
        )

    raise ValueError(
        "Authentication is required. Set both _yapi_token and _yapi_uid, "
        "or provide YAPI_TOKEN as full Cookie string."
    )


class YApiBackend:
    def __init__(
        self,
        base_url: Optional[str] = None,
        token: Optional[str] = None,
        yapi_token: Optional[str] = None,
        yapi_uid: Optional[str] = None,
        timeout: Optional[int] = None,
    ):
        self.base_url = (base_url or os.environ.get("YAPI_BASE_URL", _DEFAULT_BASE_URL)).rstrip("/")
        raw_cookie = token or os.environ.get("YAPI_TOKEN", "")
        token_part = yapi_token or os.environ.get("_yapi_token", "")
        uid_part = yapi_uid or os.environ.get("_yapi_uid", "")
        self._cookie = _build_cookie(raw_cookie, token_part, uid_part)
        self._timeout = timeout if timeout is not None else _DEFAULT_TIMEOUT

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _get(self, path: str, params: dict) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Cookie": self._cookie}
        resp = requests.get(url, params=params, headers=headers, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode", 0) != 0:
            errmsg = data.get("errmsg", "unknown")
            if "登录" in errmsg or "token" in errmsg.lower() or "auth" in errmsg.lower():
                raise RuntimeError(
                    f"YApi authentication failed: {errmsg}. "
                    "Please refresh Cookie and ensure _yapi_token and _yapi_uid are complete."
                )
            raise RuntimeError(f"YApi error {data.get('errcode')}: {errmsg}")
        return data

    def _post(self, path: str, json_body: dict) -> dict:
        url = f"{self.base_url}{path}"
        headers = {"Content-Type": "application/json", "Cookie": self._cookie}
        json_body = dict(json_body)
        resp = requests.post(url, json=json_body, headers=headers, timeout=self._timeout)
        resp.raise_for_status()
        data = resp.json()
        if data.get("errcode", 0) != 0:
            errmsg = data.get("errmsg", "unknown")
            if "登录" in errmsg or "token" in errmsg.lower() or "auth" in errmsg.lower():
                raise RuntimeError(
                    f"YApi authentication failed: {errmsg}. "
                    "Please refresh Cookie and ensure _yapi_token and _yapi_uid are complete."
                )
            raise RuntimeError(f"YApi error {data.get('errcode')}: {errmsg}")
        return data

    def discover_projects(self) -> list[dict]:
        """Discover projects available to the current Cookie session."""
        projects: dict[str, dict] = {}

        try:
            data = self._get("/api/project/list", {"page": 1, "limit": 1000})
            items = data.get("data", {}).get("list", []) if isinstance(data.get("data"), dict) else []
            for item in items:
                pid = str(item.get("_id", "")).strip()
                if pid:
                    projects[pid] = item
        except RuntimeError:
            # Some YApi deployments require group_id for /api/project/list.
            pass

        if not projects:
            groups = self._get("/api/group/list", {}).get("data", [])
            for group in groups:
                group_id = group.get("_id")
                if group_id is None:
                    continue
                try:
                    data = self._get("/api/project/list", {"group_id": group_id, "page": 1, "limit": 1000})
                except RuntimeError:
                    continue
                items = data.get("data", {}).get("list", []) if isinstance(data.get("data"), dict) else []
                for item in items:
                    pid = str(item.get("_id", "")).strip()
                    if pid:
                        projects[pid] = item

        return list(projects.values())

    def configured_project_ids(self) -> list[str]:
        """Return project IDs discovered from the current Cookie session."""
        return [str(item.get("_id")) for item in self.discover_projects() if item.get("_id") is not None]

    # ------------------------------------------------------------------
    # Public API methods
    # ------------------------------------------------------------------

    def get_api(self, project_id: str, api_id: str) -> dict:
        """GET /api/interface/get — fetch a single API by ID."""
        data = self._get("/api/interface/get", {"id": api_id})
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
        params: dict = {"project_id": project_id, "page": page, "limit": limit}
        if keyword:
            params["q"] = keyword
        if path:
            params["path"] = path
        data = self._get("/api/interface/list", params)
        return data.get("data", data)

    def get_project_info(self, project_id: str) -> dict:
        """GET /api/project/get — fetch project metadata."""
        data = self._get("/api/project/get", {"id": project_id})
        return data.get("data", data)

    def get_category_list(self, project_id: str) -> list:
        """GET /api/interface/getCatMenu — list categories for a project."""
        data = self._get("/api/interface/getCatMenu", {"project_id": project_id})
        return data.get("data", [])

    def get_category_apis(
        self,
        project_id: str,
        cat_id: str,
        page: int = 1,
        limit: int = 100,
    ) -> list:
        """GET /api/interface/list_cat — list APIs in a category."""
        data = self._get(
            "/api/interface/list_cat",
            {"catid": cat_id, "page": page, "limit": limit},
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
        endpoint = "/api/interface/up" if params.get("id") else "/api/interface/add"
        data = self._post(endpoint, params)
        return data.get("data", data)
