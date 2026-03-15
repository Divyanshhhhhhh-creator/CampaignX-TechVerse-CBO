"""
CampaignX — Dynamic OpenAPI Discovery.

Parses an OpenAPI JSON/YAML specification at RUNTIME and converts
each endpoint into a LangChain StructuredTool.  No API URLs are
hardcoded anywhere in agent code — all discovery flows through this module.

This is the CRITICAL component that avoids hackathon disqualification
for deterministic / hardcoded API calling.
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

import httpx
import yaml
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model


# ─── Spec Loader ──────────────────────────────────────────────────────────────


def load_openapi_spec(spec_path: str) -> Dict[str, Any]:
    """
    Load and parse an OpenAPI spec from a JSON or YAML file.

    Args:
        spec_path: Absolute or relative path to the spec file.

    Returns:
        Parsed spec as a Python dict.
    """
    path = Path(spec_path)
    raw = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        return yaml.safe_load(raw)
    else:
        return json.loads(raw)


# ─── Pydantic Model Builder ──────────────────────────────────────────────────


_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def _schema_to_pydantic_fields(
    parameters: List[Dict[str, Any]],
    body_schema: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Convert OpenAPI parameters + requestBody schema into
    Pydantic model field definitions for create_model().
    """
    fields: Dict[str, Any] = {}

    # Query / path parameters
    for param in parameters:
        name = param["name"]
        schema = param.get("schema", {})
        py_type = _TYPE_MAP.get(schema.get("type", "string"), str)
        required = param.get("required", False)
        description = param.get("description", "")
        default = schema.get("default", ... if required else None)
        fields[name] = (
            py_type if required else Optional[py_type],
            Field(default=default, description=description),
        )

    # Request body properties
    if body_schema:
        props = body_schema.get("properties", {})
        required_fields = set(body_schema.get("required", []))
        for prop_name, prop_schema in props.items():
            py_type = _TYPE_MAP.get(prop_schema.get("type", "string"), str)
            description = prop_schema.get("description", "")
            is_required = prop_name in required_fields
            default = ... if is_required else None
            fields[prop_name] = (
                py_type if is_required else Optional[py_type],
                Field(default=default, description=description),
            )

    return fields


# ─── Dynamic Tool Factory ────────────────────────────────────────────────────


def _make_api_caller(
    method: str,
    url_template: str,
    parameters: List[Dict[str, Any]],
    has_body: bool,
) -> Callable:
    """
    Create a closure that calls the API endpoint dynamically.
    Adds cache-busting timestamp to GET requests.
    """

    def call_api(**kwargs: Any) -> str:
        # Separate query params from body params
        query_params: Dict[str, Any] = {}
        body_params: Dict[str, Any] = {}
        param_names = {p["name"] for p in parameters}

        for key, value in kwargs.items():
            if value is None:
                continue
            if key in param_names:
                query_params[key] = value
            else:
                body_params[key] = value

        # Cache busting for GET requests (force fresh cohort data)
        if method.upper() == "GET":
            query_params["_t"] = str(int(time.time() * 1000))

        url = url_template
        
        # Inject API Key automatically (skip for signup route)
        headers = {}
        if not url.endswith("/signup"):
            api_key = os.getenv("CAMPAIGNX_API_KEY", "")
            if api_key:
                headers["X-API-Key"] = api_key

        try:
            with httpx.Client(timeout=30.0, headers=headers) as client:
                if method.upper() == "GET":
                    resp = client.get(url, params=query_params)
                elif method.upper() == "POST":
                    resp = client.post(url, params=query_params, json=body_params)
                elif method.upper() == "PUT":
                    resp = client.put(url, params=query_params, json=body_params)
                elif method.upper() == "DELETE":
                    resp = client.delete(url, params=query_params)
                else:
                    return json.dumps({"error": f"Unsupported method: {method}"})

                resp.raise_for_status()
                return resp.text
        except httpx.HTTPStatusError as e:
            return json.dumps({
                "error": f"HTTP {e.response.status_code}",
                "detail": e.response.text[:500],
            })
        except Exception as e:
            return json.dumps({"error": str(e)})

    return call_api


def build_tools_from_spec(
    spec: Dict[str, Any],
    base_url: Optional[str] = None,
) -> Dict[str, StructuredTool]:
    """
    Parse an OpenAPI spec and create a StructuredTool for each endpoint.

    Args:
        spec:     Parsed OpenAPI spec dict.
        base_url: Override the server URL from the spec.  Falls back
                  to the first ``servers[].url`` entry.

    Returns:
        Dict mapping operationId → StructuredTool.
    """
    if base_url is None:
        servers = spec.get("servers", [])
        base_url = servers[0]["url"] if servers else "http://127.0.0.1:8000"

    tools: Dict[str, StructuredTool] = {}

    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.lower() not in ("get", "post", "put", "delete", "patch"):
                continue

            op_id = operation.get("operationId")
            if not op_id:
                # Auto-generate from method + path
                op_id = f"{method}_{path.replace('/', '_').strip('_')}"

            summary = operation.get("summary", "")
            description = operation.get("description", summary)
            parameters = operation.get("parameters", [])

            # Extract request body schema
            body_schema = None
            has_body = False
            request_body = operation.get("requestBody", {})
            if request_body:
                content = request_body.get("content", {})
                json_content = content.get("application/json", {})
                body_schema = json_content.get("schema")
                has_body = body_schema is not None

            # Build Pydantic input model dynamically
            fields = _schema_to_pydantic_fields(parameters, body_schema)

            if not fields:
                # Endpoint with no params — add a dummy field
                fields["_placeholder"] = (
                    Optional[str],
                    Field(default=None, description="No parameters required"),
                )

            InputModel = create_model(f"{op_id}_Input", **fields)

            # Build the callable
            full_url = f"{base_url.rstrip('/')}{path}"
            api_caller = _make_api_caller(method, full_url, parameters, has_body)

            tool = StructuredTool.from_function(
                func=api_caller,
                name=op_id,
                description=f"{description}\n\nEndpoint: {method.upper()} {path}",
                args_schema=InputModel,
                return_direct=False,
            )
            tools[op_id] = tool

    return tools


# ─── Convenience ──────────────────────────────────────────────────────────────


def discover_api_tools(
    spec_path: str = "openapi_spec.json",
    base_url: Optional[str] = None,
) -> Dict[str, StructuredTool]:
    """
    One-call convenience: load spec → build tools.

    Usage::

        tools = discover_api_tools("openapi_spec.json", "http://127.0.0.1:8000")
        cohort_tool = tools["get_customer_cohort"]
        result = cohort_tool.invoke({"segment": "female_seniors", "no_cache": "true"})
    """
    spec = load_openapi_spec(spec_path)
    return build_tools_from_spec(spec, base_url)


def get_tool_descriptions(tools: Dict[str, StructuredTool]) -> str:
    """Return a formatted summary of all discovered tools for agent prompts."""
    lines = ["Available API Tools (dynamically discovered from OpenAPI spec):", ""]
    for name, tool in tools.items():
        lines.append(f"• {name}: {tool.description.split(chr(10))[0]}")
        if hasattr(tool, "args_schema") and tool.args_schema:
            schema = tool.args_schema.model_json_schema()
            props = schema.get("properties", {})
            for pname, pinfo in props.items():
                if pname.startswith("_"):
                    continue
                req = "required" if pname in schema.get("required", []) else "optional"
                lines.append(f"    - {pname} ({req}): {pinfo.get('description', '')}")
        lines.append("")
    return "\n".join(lines)
