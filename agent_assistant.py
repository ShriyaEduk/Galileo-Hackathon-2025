"""
This assistant has the following responsabilities:

1.- Send a request to the client's URL with the prompt to be sent.
1.1.- Store the response.

2.-Search in Galileo (either using the API or in Clickhouse) using the project name and the prompt to identify the message and the metrics.

3.- Return the response and the metrics obtained from steps 1.1 and 2.

The entry point is the function process_request.
"""

from pydantic import BaseModel
import httpx
import os
from typing import Optional


GALILEO_API_KEY = "RXjKbMVCqZ-hYvbLt9VomSnLAIWV2Y0apU8nvd4i--8"
BASE_URL = "http://localhost:8088"
# BASE_URL = "https://api.galileo.ai/v2/"


class ResponseBundle(BaseModel):
    response: str
    metrics: dict


async def send_request_to_client(url: str, prompt: str) -> str:
    """
    Send a request to the client's URL with the prompt to be sent.
    """
    return ""


async def get_project_id(project_name: str) -> Optional[str]:
    """Get project ID from project name."""
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{BASE_URL}/projects/",
            params={"project_name": project_name},
            headers={"Galileo-API-Key": GALILEO_API_KEY},
        )
        if response.status_code == 200:
            data = response.json()
            return data.get("id")
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
    project_id = await get_project_id(project_name)
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

    if traces and isinstance(traces, list) and len(traces) > 0:
        # Assuming the first trace contains the relevant information
        trace = traces[0]
        response = trace.get("output", "")
        metrics = {
            "latency": trace.get("latency", 0),
            "tokens": trace.get("tokens", 0),
            "cost": trace.get("cost", 0),
        }

    return ResponseBundle(response=response, metrics=metrics)


async def process_request(
    url: str, prompt: str, project_name: str, log_stream_name: str
) -> ResponseBundle:
    """
    Send a request to the client's URL with the prompt to be sent and return the
    response and the metrics from galileo.
    """
    response = await send_request_to_client(
        url, prompt
    )  # Not sure if we will use this response.
    response_bundle = await search_in_galileo(project_name, log_stream_name, prompt)
    return response_bundle
