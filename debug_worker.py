import asyncio
import threading
import time
import sys
from datetime import datetime

# Import our worker modules
from worker import (
    message_queue,
    start_worker_thread,
    stop_worker_thread,
    queue_attack_iteration,
    check_for_results,
    run_attack_iteration
)
from attacks import get_default_prompts

def debug_worker_flow():
    """Test the worker flow directly without Streamlit."""
    print("Starting worker thread debug test")
    
    # Start the worker thread
    print("Starting worker thread...")
    worker_thread = start_worker_thread()
    print("Worker thread started")
    
    # Prepare test parameters
    api_type = "finance-chat"
    api_base = "http://localhost:5726/api/chat"
    api_key = ""  # Not needed for finance-chat
    prompts = get_default_prompts()
    iteration_count = 0
    
    # Finance chat specific params
    kwargs = {
        "system_prompt": "You are a stock market analyst and trading assistant.",
        "model": "gpt-3.5-turbo",
        "use_rag": True,
        "namespace": "sp500-qa-demo"
    }
    
    # Queue an attack iteration
    print(f"Queueing attack iteration {iteration_count}...")
    queue_attack_iteration(
        api_type, api_base, api_key, prompts, iteration_count, **kwargs
    )
    print("Attack iteration queued")
    
    # Wait for result
    print("Waiting for result...")
    max_wait_time = 60  # seconds
    start_time = time.time()
    result_received = False
    
    while time.time() - start_time < max_wait_time:
        result = check_for_results()
        if result:
            print(f"Result received after {time.time() - start_time:.2f} seconds")
            print(f"Result action: {result['action']}")
            
            if result['action'] == 'iteration_result':
                iteration_data = result['result']
                print(f"Prompt: {iteration_data['prompt'][:100]}...")
                print(f"Response: {iteration_data['response'][:100]}...")
                print(f"Metrics: {iteration_data['metrics']}")
            elif result['action'] in ['iteration_error', 'worker_error']:
                print(f"Error: {result.get('error', 'Unknown error')}")
            
            result_received = True
            break
        
        # Small sleep to avoid tight loop
        time.sleep(0.5)
        sys.stdout.write(".")
        sys.stdout.flush()
    
    if not result_received:
        print(f"No result received after {max_wait_time} seconds")
    
    # Clean up
    print("Stopping worker thread...")
    stop_worker_thread()
    worker_thread.join(timeout=5)
    print("Worker thread stopped")
    
    return result_received

def debug_direct_api_call():
    """Test a direct API call without using the worker thread."""
    print("\nTesting direct API call...")
    
    # Prepare test parameters
    api_type = "finance-chat"
    api_base = "http://localhost:5726/api/chat"
    api_key = ""  # Not needed for finance-chat
    prompts = get_default_prompts()
    iteration_count = 0
    
    # Finance chat specific params
    kwargs = {
        "system_prompt": "You are a stock market analyst and trading assistant.",
        "model": "gpt-3.5-turbo",
        "use_rag": True,
        "namespace": "sp500-qa-demo"
    }
    
    # Run the async function directly
    async def run_test():
        print("Running direct API call...")
        try:
            result = await run_attack_iteration(
                api_type, api_base, api_key, prompts, iteration_count, **kwargs
            )
            print(f"Direct API call result:")
            print(f"Prompt: {result['prompt'][:100]}...")
            print(f"Response: {result['response'][:100]}...")
            print(f"Metrics: {result['metrics']}")
            return True
        except Exception as e:
            print(f"Error in direct API call: {str(e)}")
            return False
    
    # Run the async function
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    success = loop.run_until_complete(run_test())
    loop.close()
    
    return success

if __name__ == "__main__":
    print("WORKER FLOW TEST")
    print("=" * 80)
    worker_success = debug_worker_flow()
    print("\n\nDIRECT API CALL TEST")
    print("=" * 80)
    api_success = debug_direct_api_call()
    
    print("\n\nTEST RESULTS:")
    print(f"Worker flow test: {'SUCCESS' if worker_success else 'FAILED'}")
    print(f"Direct API call test: {'SUCCESS' if api_success else 'FAILED'}") 