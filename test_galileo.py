#!/usr/bin/env python3
"""
Test script for Galileo integration functions
"""

import os
import asyncio
from agent_assistant import get_project_id_post, get_log_stream_id, search_traces, search_in_galileo
from metrics import get_metrics_and_reasoning, get_metrics_and_reasoning_async

# Set environment variables if not already set
if not os.environ.get("GALILEO_API_KEY"):
    os.environ["GALILEO_API_KEY"] = "t7l6DEn3GiuXyQgF-w68ELn7XnzK4ixMe7T1C8WU370"
    
if not os.environ.get("GALILEO_API_BASE_URL"):
    os.environ["GALILEO_API_BASE_URL"] = "https://app.galileo.ai/api/galileo/v2"

async def test_galileo_search():
    """Test the Galileo search functionality"""
    project_name = "pawan-demo-app"
    log_stream_name = "default"
    prompt = "Give me a good example of investment"
    
    print(f"\n=== Testing with project={project_name}, log_stream={log_stream_name}, prompt='{prompt}' ===\n")
    
    # Test get_project_id_post
    print("1. Getting project ID...")
    project_id = await get_project_id_post(project_name)
    print(f"Project ID: {project_id}")
    
    if not project_id:
        print("Could not find project ID. Check project name and API key.")
        return
    
    # Test get_log_stream_id
    print("\n2. Getting log stream ID...")
    log_stream_id = await get_log_stream_id(project_id, log_stream_name)
    print(f"Log Stream ID: {log_stream_id}")
    
    if not log_stream_id:
        print("Could not find log stream ID. Check log stream name.")
        return
    
    # Test search_traces
    print("\n3. Searching traces...")
    traces = await search_traces(project_id, log_stream_id, prompt)
    records = traces.get("records", [])
    print(f"Found {len(records)} matching traces")
    
    if records:
        first_trace = records[0]
        print(f"First trace ID: {first_trace.get('id')}")
        print(f"First trace input: {first_trace.get('input')[:50]}...")
        print(f"First trace output: {first_trace.get('output')[:50]}...")
    
    # Test search_in_galileo
    print("\n4. Testing search_in_galileo...")
    response_bundle = await search_in_galileo(project_name, log_stream_name, prompt)
    print(f"Response bundle response length: {len(response_bundle.response)}")
    print(f"Response bundle metrics: {response_bundle.metrics}")
    print(f"Response bundle metric_info: {response_bundle.metric_info}")
    
    # Test metrics.get_metrics_and_reasoning_async (the async version)
    print("\n5. Testing get_metrics_and_reasoning_async...")
    metrics = await get_metrics_and_reasoning_async(prompt, project_name, log_stream_name)
    print(f"Metrics (async): {metrics}")
    
    print("\n=== Test complete ===")

if __name__ == "__main__":
    asyncio.run(test_galileo_search()) 