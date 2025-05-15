"""
This assistant will look in the galileo trace for the response and the metrics.
The entry point is the function process_request.
"""

import os
from typing import Optional

import httpx
from pydantic import BaseModel

GALILEO_API_KEY = os.getenv("GALILEO_API_KEY")
BASE_URL = os.getenv("GALILEO_API_BASE_URL")


class ResponseBundle(BaseModel):
    response: str
    metrics: dict
    metric_info: dict


async def get_project_id(project_name: str) -> Optional[str]:
    """
    Get project ID from project name using a POST request with filters.
    """
    url = f"{BASE_URL}/projects"
    payload = {
        "filters": [
            {
                "name": "name",
                "operator": "eq",
                "value": project_name,
                "case_sensitive": True,
            }
        ],
        "sort": {"name": "created_at", "ascending": False, "sort_type": "column"},
    }
    headers = {
        "accept": "*/*",
        "galileo-api-key": GALILEO_API_KEY,
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL,
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/projects",
            json=payload,
            headers=headers,
        )
        if response.status_code == 200:
            data = response.json()
            projects = data.get("projects", [])
            if projects:
                return projects[0].get("id")
    return None


async def get_project_id_post(project_name: str) -> Optional[str]:
    """
    Get project ID from project name using a POST request with filters.
    """
    url = f"{BASE_URL}/projects"
    payload = {
        "filters": [
            {
                "name": "name",
                "operator": "eq",
                "value": project_name,
                "case_sensitive": True,
            }
        ],
        "sort": {"name": "created_at", "ascending": False, "sort_type": "column"},
    }
    headers = {
        "accept": "*/*",
        "galileo-api-key": GALILEO_API_KEY,
        "content-type": "application/json",
        "origin": BASE_URL,
        "referer": BASE_URL,
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "user-agent": "Mozilla/5.0",
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(url, json=payload, headers=headers)
        if response.status_code == 200:
            data = response.json()
            projects = data.get("projects", [])
            if projects:
                return projects[0].get("id")
    return None


async def get_log_stream_id(project_id: str, log_stream_name: str) -> Optional[str]:
    """Get log stream ID from project ID and log stream name."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/projects/{project_id}/log_streams",
            headers={"Galileo-API-Key": GALILEO_API_KEY},
        )
        if response.status_code == 200:
            data = response.json()
            for stream in data:
                if stream.get("name") == log_stream_name:
                    return stream.get("id")
    return None


async def search_traces(project_id: str, log_stream_id: str, prompt: str) -> dict:
    """Search traces using project ID, log stream ID and prompt."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/projects/{project_id}/traces/search",
            headers={
                "Galileo-API-Key": GALILEO_API_KEY,
                "Content-Type": "application/json",
            },
            json={
                "log_stream_id": log_stream_id,
                "filters": [
                    {
                        "case_sensitive": False,
                        "name": "input",
                        "operator": "contains",
                        "type": "text",
                        "value": prompt,
                    }
                ],
            },
        )
        if response.status_code == 200:
            return response.json()
    return {}


async def search_in_galileo(
    project_name: str, log_stream_name: str, prompt: str
) -> ResponseBundle:
    """
    Search in Galileo (either using the API or in Clickhouse) using the project
    name and the prompt to identify the message and the metrics.
    """
    # Get project ID
    project_id = await get_project_id_post(project_name)
    if not project_id:
        return ResponseBundle(response="Project not found", metrics={})

    # Get log stream ID
    log_stream_id = await get_log_stream_id(project_id, log_stream_name)
    if not log_stream_id:
        return ResponseBundle(response="Log stream not found", metrics={})

    # Search traces
    traces = await search_traces(project_id, log_stream_id, prompt)

    # Extract response and metrics from traces
    response = ""
    metrics = {}

    if traces:
        # Assuming the first trace record contains the relevant information
        response = traces.get("records", [])
        trace = response[0] if response else {}
        response = trace.get("output", "")
        metrics = trace.get("metrics", {})
        metric_info = trace.get("metric_info", {})

    return ResponseBundle(response=response, metrics=metrics, metric_info=metric_info)
