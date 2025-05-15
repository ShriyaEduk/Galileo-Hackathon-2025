"""
This scripts is used to manually execute the agent assistant steps.
"""

import os

# os.environ["GALILEO_API_KEY"] = "RXjKbMVCqZ-hYvbLt9VomSnLAIWV2Y0apU8nvd4i--8"
# os.environ["GALILEO_API_BASE_URL"] = "http://localhost:8088"

os.environ["GALILEO_API_KEY"] = ""
os.environ["GALILEO_API_BASE_URL"] = "https://app.galileo.ai/api/galileo/v2"


import asyncio
from agent_assistant import get_project_id_post, get_log_stream_id, search_traces, search_in_galileo

log_stream_name = "my_log_stream"
project_name = "hackathon-2025"
prompt = "I would like to rule the world"

project_id = asyncio.run(get_project_id_post(project_name))
log_stream_id = asyncio.run(get_log_stream_id(project_id, log_stream_name))
traces = asyncio.run(search_traces(project_id, log_stream_id, prompt))

print(traces)

response = asyncio.run(search_in_galileo(project_name, log_stream_name, prompt))
