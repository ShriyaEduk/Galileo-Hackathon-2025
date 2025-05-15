import asyncio
import queue
import threading
from datetime import datetime

# Import other modules
from attacks import start_attack
from api import send_api_request
from metrics import get_metrics_and_reasoning
from storage import persist_chat_history

# Create a message queue for communication between threads
message_queue = queue.Queue()

async def run_attack_iteration(api_type, api_base, api_key, prompts, iteration_count, **kwargs):
    """Run a single iteration of the attack loop and return the results."""
    try:
        print(f"DEBUG: Starting attack iteration {iteration_count}")
        # Generate the adversarial prompt
        prompt = start_attack(prompts, iteration_count)
        print(f"DEBUG: Generated prompt: {prompt[:50]}...")
        
        # Send to API and get response
        if api_type == "finance-chat":
            # Get finance-chat specific params
            system_prompt = kwargs.get("system_prompt", "")
            model = kwargs.get("model", "gpt-4")
            use_rag = kwargs.get("use_rag", True)
            namespace = kwargs.get("namespace", "sp500-qa-demo")
            
            print(f"DEBUG: Sending request to finance-chat API at {api_base}")
            response = await send_api_request(
                api_type, api_base, api_key, prompt,
                system_prompt=system_prompt, 
                model=model, 
                use_rag=use_rag, 
                namespace=namespace
            )
            print(f"DEBUG: Received response from finance-chat API: {response[:100]}...")
        else:
            # Normal OpenAI API
            print(f"DEBUG: Sending request to OpenAI API at {api_base}")
            response = await send_api_request(api_type, api_base, api_key, prompt)
            print(f"DEBUG: Received response from OpenAI API: {response[:100]}...")
        
        # Check if the response indicates an error
        if isinstance(response, str) and response.startswith("Error:"):
            print(f"API error detected: {response}")
        
        # Get metrics
        print("DEBUG: Getting metrics and reasoning")
        metrics = get_metrics_and_reasoning(response)
        print(f"DEBUG: Got metrics: {metrics}")
        
        print(f"DEBUG: Completing iteration {iteration_count}")
        return {
            "prompt": prompt,
            "response": response,
            "metrics": metrics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Exception in run_attack_iteration: {str(e)}")
        # Return a result that includes the error information
        return {
            "prompt": prompt if 'prompt' in locals() else "Error occurred before prompt generation",
            "response": f"Error in attack iteration: {str(e)}",
            "metrics": {"score": 0.0, "reasoning": f"Error: {str(e)}"},
            "timestamp": datetime.now().isoformat()
        }

def background_worker():
    """Background worker that processes attack iterations."""
    print("DEBUG: Starting background worker thread")
    while True:
        try:
            # Get the next task from the queue
            task = message_queue.get(block=True, timeout=0.5)
            print(f"DEBUG: Got task from queue: {task['action']}")
            
            if task["action"] == "stop":
                # Stop signal received
                print("DEBUG: Got stop signal, stopping worker thread")
                break
            
            if task["action"] == "run_iteration":
                # Run a single attack iteration
                api_type = task["api_type"]
                api_base = task["api_base"]
                api_key = task["api_key"]
                prompts = task["prompts"]
                iteration_count = task["iteration_count"]
                kwargs = task.get("kwargs", {})
                
                print(f"DEBUG: Starting run_iteration task for iteration {iteration_count}")
                
                # Run the async task
                try:
                    async def run_task():
                        try:
                            print(f"DEBUG: Running async task for iteration {iteration_count}")
                            result = await run_attack_iteration(
                                api_type, api_base, api_key, prompts, iteration_count, **kwargs
                            )
                            # Put the result back in the queue
                            print(f"DEBUG: Putting result in queue for iteration {iteration_count}")
                            message_queue.put({
                                "action": "iteration_result",
                                "result": result,
                                "iteration_count": iteration_count
                            })
                            print(f"DEBUG: Result added to queue for iteration {iteration_count}")
                        except Exception as e:
                            print(f"Error in async task: {str(e)}")
                            # Report error back through the queue
                            message_queue.put({
                                "action": "iteration_error",
                                "error": str(e),
                                "iteration_count": iteration_count
                            })
                    
                    # Run the async task
                    print(f"DEBUG: Starting asyncio.run for iteration {iteration_count}")
                    asyncio.run(run_task())
                    print(f"DEBUG: Completed asyncio.run for iteration {iteration_count}")
                except Exception as e:
                    print(f"Error running async task: {str(e)}")
                    # Report error back through the queue
                    message_queue.put({
                        "action": "iteration_error",
                        "error": str(e),
                        "iteration_count": iteration_count
                    })
            
            # Mark the task as done
            message_queue.task_done()
            
        except queue.Empty:
            # No tasks in the queue, continue waiting
            continue
        except Exception as e:
            # Log any errors
            print(f"Error in background worker: {str(e)}")
            try:
                # Try to report the error
                message_queue.put({
                    "action": "worker_error",
                    "error": str(e)
                })
            except:
                pass

def start_worker_thread():
    """Start the background worker thread if not already running."""
    worker_thread = threading.Thread(target=background_worker)
    worker_thread.daemon = True
    worker_thread.start()
    return worker_thread

def stop_worker_thread():
    """Signal the worker thread to stop."""
    message_queue.put({"action": "stop"})

def queue_attack_iteration(api_type, api_base, api_key, prompts, iteration_count, **kwargs):
    """Queue an attack iteration to be processed by the worker thread."""
    message_queue.put({
        "action": "run_iteration",
        "api_type": api_type,
        "api_base": api_base,
        "api_key": api_key,
        "prompts": prompts,
        "iteration_count": iteration_count,
        "kwargs": kwargs
    })

def check_for_results():
    """Check for results from the background worker."""
    try:
        # Non-blocking check for results
        print("DEBUG: Checking for results in the queue")
        result = message_queue.get_nowait()
        print(f"DEBUG: Got result from queue: {result['action']}")
        message_queue.task_done()
        return result
    except queue.Empty:
        # No results yet
        return None
    except Exception as e:
        print(f"Error checking for results: {str(e)}")
        return None 