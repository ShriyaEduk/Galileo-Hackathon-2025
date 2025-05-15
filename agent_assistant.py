"""
This assistant has the following responsabilities:

1.- Send a request to the client's URL with the prompt to be sent.
1.1.- Store the response.

2.-Search in Galileo (either using the API or in Clickhouse) using the project name and the prompt to identify the message and the metrics.

3.- Return the response and the metrics obtained from steps 1.1 and 2.

The entry point is the function process_request.
"""

from pydantic import BaseModel


class ResponseBundle(BaseModel):
    response: str
    metrics: dict


async def send_request_to_client(url: str, prompt: str) -> str:
    """
    Send a request to the client's URL with the prompt to be sent.
    """
    return ""


async def search_in_galileo(
    project_name: str, log_stream_name: str, prompt: str
) -> ResponseBundle:
    """
    Search in Galileo (either using the API or in Clickhouse) using the project
    name and the prompt to identify the message and the metrics.
    """
    return ResponseBundle(response="", metrics={})


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
