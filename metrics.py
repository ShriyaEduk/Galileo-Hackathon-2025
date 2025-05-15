import asyncio
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def get_metrics_and_reasoning_async(prompt: str, 
                               project_name: str = "hackathon-2025", 
                               log_stream_name: str = "my_log_stream") -> Dict[str, Any]:
    """
    Get metrics and reasoning based on a prompt by searching Galileo traces.
    
    Args:
        prompt: The prompt to search for
        project_name: The Galileo project name
        log_stream_name: The name of the log stream
        
    Returns:
        Dictionary containing metrics and reasoning
    """
    # Import here to avoid circular imports
    from agent_assistant import get_project_id_post, get_log_stream_id, search_traces
    
    # Get project and log stream IDs
    project_id = await get_project_id_post(project_name)
    if not project_id:
        return {
            "score": 0.0,
            "reasoning": f"Project {project_name} not found"
        }
        
    log_stream_id = await get_log_stream_id(project_id, log_stream_name)
    if not log_stream_id:
        return {
            "score": 0.0,
            "reasoning": f"Log stream {log_stream_name} not found"
        }
    
    # Search for traces
    traces = await search_traces(project_id, log_stream_id, prompt)
    
    trace_records = traces.get("records", [])
    if not trace_records:
        return {
            "score": 0.0,
            "reasoning": "No matching traces found for the given prompt."
        }
    
    # Extract metrics from the most recent trace
    latest_trace = trace_records[0]  # Assuming results are sorted by recency
    
    # Example metric calculation - customize based on your actual requirements
    score = min(len(trace_records) / 10.0, 1.0)  # Simple score based on number of traces
    
    return {
        "score": score,
        "reasoning": f"Found {len(trace_records)} relevant traces for the given prompt.",
        "trace_count": len(trace_records),
        "trace_id": latest_trace.get("id"),
        "duration_ms": latest_trace.get("duration_ns", 0) / 1000000,
        "latest_output": latest_trace.get("output", "")[:100] + "..." if len(latest_trace.get("output", "")) > 100 else latest_trace.get("output", "")
    }

def get_metrics_and_reasoning(prompt_or_response, 
                              project_name: str = "hackathon-2025", 
                              log_stream_name: str = "my_log_stream") -> Dict[str, Any]:
    """
    Wrapper for get_metrics_and_reasoning_async that accepts either a prompt or a response.
    
    If the parameter is a string, it's treated as a prompt to search for.
    If it's already a response dict, we extract useful metrics from it.
    
    Args:
        prompt_or_response: Either the prompt string to search for, or a response object
        project_name: The Galileo project name
        log_stream_name: The name of the log stream
        
    Returns:
        Dictionary containing metrics and reasoning
    """
    # If we received a response object instead of a prompt string, extract metrics from it
    if not isinstance(prompt_or_response, str):
        try:
            # If it's a dict with metrics, return those
            if hasattr(prompt_or_response, 'metrics') and prompt_or_response.metrics:
                return prompt_or_response.metrics
            
            # If it has a 'response' attribute that's a string, use that as our prompt
            if hasattr(prompt_or_response, 'response') and isinstance(prompt_or_response.response, str):
                prompt = prompt_or_response.response
            else:
                # Default fallback
                return {
                    "score": 0.0,
                    "reasoning": "Invalid response format for metrics calculation."
                }
        except (AttributeError, TypeError):
            return {
                "score": 0.0,
                "reasoning": "Unable to extract metrics from the response."
            }
    else:
        # It's a string, treat it as a prompt
        prompt = prompt_or_response
    
    # Check if we're already in an event loop
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            logger.info("Already in an event loop, creating a new one is not safe")
            # We're already in an event loop, can't use asyncio.run()
            # Return a placeholder until we can properly handle this case
            return {
                "score": 0.5,
                "reasoning": "Metrics calculation inside an existing event loop is not implemented properly. Use the async version directly."
            }
        else:
            # Run the async function synchronously
            return asyncio.run(get_metrics_and_reasoning_async(prompt, project_name, log_stream_name))
    except Exception as e:
        logger.error(f"Error calculating metrics: {str(e)}")
        return {
            "score": 0.0,
            "reasoning": f"Error calculating metrics: {str(e)}"
        } 