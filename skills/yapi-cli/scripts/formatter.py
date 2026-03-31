"""YApi response formatter — cleans and reduces API data for agent use.

Apply via ``format_api_data()`` when ``--pure`` is requested.
By default the CLI returns raw API data from YApi unchanged.
"""

import json


_GATEWAY_PARAMS = {"uid", "puid", "pid", "_uid"}


def _clean_req_query(req_query: list) -> list:
    """Filter out gateway-layer parameters from req_query list."""
    if not isinstance(req_query, list):
        return req_query
    return [
        param
        for param in req_query
        if isinstance(param, dict) and param.get("name") not in _GATEWAY_PARAMS
    ]


def _clean_req_body_other(req_body_other: str | dict) -> str | dict:
    """Remove gateway-layer properties from req_body_other JSON schema."""
    if not req_body_other:
        return req_body_other
    try:
        if isinstance(req_body_other, str):
            schema = json.loads(req_body_other)
        else:
            schema = req_body_other

        if not isinstance(schema, dict) or "properties" not in schema:
            return req_body_other

        props = schema.get("properties", {})
        for key in _GATEWAY_PARAMS:
            props.pop(key, None)

        if isinstance(req_body_other, str):
            return json.dumps(schema, ensure_ascii=False)
        return schema
    except (json.JSONDecodeError, TypeError):
        return req_body_other


def _clean_res_body(res_body: str | dict) -> str | dict:
    """Extract the data field from response body schema when present."""
    if not res_body:
        return res_body
    try:
        if isinstance(res_body, str):
            schema = json.loads(res_body)
        else:
            schema = res_body

        if not isinstance(schema, dict):
            return res_body

        props = schema.get("properties", {})
        if "data" in props:
            data_schema = props["data"]
            return (
                data_schema
                if isinstance(res_body, dict)
                else json.dumps(data_schema, ensure_ascii=False)
            )
        return res_body
    except (json.JSONDecodeError, TypeError):
        return res_body


def format_api_data(api_data: dict) -> dict:
    """Return a cleaned, reduced view of *api_data* for agent consumption.

    Keeps only: path, method, title, req_query, req_body_other,
    res_body_type, res_body.
    Strips gateway-layer parameters (uid/puid/pid/_uid) from query and body,
    and unwraps the ``data`` field from response schema when present.
    """
    if not isinstance(api_data, dict):
        return api_data

    result: dict = {
        "path": api_data.get("path"),
        "method": api_data.get("method"),
        "title": api_data.get("title"),
    }

    req_query = api_data.get("req_query")
    if req_query:
        result["req_query"] = _clean_req_query(req_query)

    req_body = api_data.get("req_body_other")
    if req_body:
        result["req_body_other"] = _clean_req_body_other(req_body)

    if "res_body_type" in api_data:
        result["res_body_type"] = api_data["res_body_type"]

    res_body = api_data.get("res_body")
    if res_body:
        result["res_body"] = _clean_res_body(res_body)

    return result
