import aiohttp
import uuid
import asyncio
import time
import requests
import json
import openai

async def send_openai_api_request(api_base, api_key, message):
    """Send a request to the OpenAI API and return the response."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": "gpt-3.5-turbo",
        "messages": [{"role": "user", "content": message}],
        "temperature": 0.7
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(api_base, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"Error: {response.status} - {await response.text()}"

def send_finance_chat_sync(api_base, message, system_prompt, model, use_rag, namespace):
    """Synchronous version of send_finance_chat_api_request."""
    print(f"DEBUG API: Running synchronous Finance Chat API request")
    
    headers = {
        "Content-Type": "application/json"
    }
    
    # Create a unique session ID for each request
    session_id = f"agent-smith-{uuid.uuid4()}"
    
    payload = {
        "session_id": session_id,
        "message": message,
        "system_prompt": system_prompt,
        "model": model,
        "use_rag": use_rag,
        "namespace": namespace
    }
    
    print(f"DEBUG API: Sync payload prepared: session_id={session_id}, message={message[:50]}...")
    
    try:
        print(f"DEBUG API: Sending sync POST request to {api_base}")
        start_time = time.time()
        response = requests.post(api_base, headers=headers, json=payload, timeout=60)
        print(f"DEBUG API: Got sync response with status {response.status_code} after {time.time() - start_time:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            
            # Extract the response text from the JSON
            if "response" in data:
                return data.get("response", "No response received")
            elif "conversation" in data:
                # Find the last assistant message in the conversation
                assistant_messages = [
                    msg for msg in data["conversation"] 
                    if msg.get("role") == "assistant" and msg.get("content")
                ]
                if assistant_messages:
                    # Return the most recent assistant message
                    return assistant_messages[-1].get("content", "")
                else:
                    return "No assistant response found in the conversation."
            else:
                return f"Error: Response format not recognized: {str(data)[:200]}..."
        else:
            return f"Error: HTTP {response.status_code} - {response.text[:200]}..."
    except Exception as e:
        print(f"DEBUG API Sync: Error: {str(e)}")
        return f"Error in sync API request: {str(e)}"

async def send_finance_chat_api_request(api_base, message, system_prompt, model, use_rag, namespace):
    """Send a request to the Finance Chat API and return the response."""
    print(f"DEBUG API: Preparing request to {api_base}")
    headers = {
        "Content-Type": "application/json"
    }
    
    # Create a unique session ID for each request
    session_id = f"agent-smith-{uuid.uuid4()}"
    
    payload = {
        "session_id": session_id,
        "message": message,
        "system_prompt": system_prompt,
        "model": model,
        "use_rag": use_rag,
        "namespace": namespace
    }
    
    print(f"DEBUG API: Payload prepared: session_id={session_id}, message={message[:50]}...")
    
    print(f"DEBUG API: Sending POST request to {api_base}")
    start_time = time.time()
    
    try:
        # Use synchronous requests instead of aiohttp
        response = requests.post(api_base, headers=headers, json=payload, timeout=60)
        
        print(f"DEBUG API: Got response with status {response.status_code} after {time.time() - start_time:.2f} seconds")
        
        if response.status_code == 200:
            try:
                data = response.json()
                print(f"DEBUG API: Successfully parsed JSON response")
                
                # For debugging purposes, print the full response
                print(f"DEBUG API: Full response: {json.dumps(data)[:500]}...")
                
                # Extract the response text from the JSON
                # The Finance Chat API returns a conversation object with the latest response
                if "response" in data:
                    print(f"DEBUG API: Response contains 'response' field: {data['response'][:100]}...")
                    return data.get("response", "No response received")
                elif "conversation" in data:
                    # Find the last assistant message in the conversation
                    assistant_messages = [
                        msg for msg in data["conversation"] 
                        if msg.get("role") == "assistant" and msg.get("content")
                    ]
                    if assistant_messages:
                        # Return the most recent assistant message
                        response_text = assistant_messages[-1].get("content", "")
                        print(f"DEBUG API: Extracted assistant response: {response_text[:100]}...")
                        return response_text
                    else:
                        print(f"DEBUG API: No assistant message found in response")
                        return "No assistant response found in the conversation."
                else:
                    print(f"DEBUG API: Response missing expected fields, raw data: {str(data)[:200]}...")
                    return f"Error: Response format not recognized: {str(data)[:200]}..."
            except Exception as e:
                print(f"DEBUG API: Error parsing JSON: {str(e)}")
                raw_text = response.text
                print(f"DEBUG API: Raw response text: {raw_text[:200]}...")
                return f"Error parsing response: {str(e)}, raw: {raw_text[:200]}..."
        else:
            error_text = response.text
            print(f"DEBUG API: Error response ({response.status_code}): {error_text[:200]}...")
            return f"Error: HTTP {response.status_code} - {error_text[:200]}..."
            
    except requests.exceptions.ConnectTimeout:
        print(f"DEBUG API: Connection timeout after {time.time() - start_time:.2f} seconds")
        return f"Connection timeout: The request to {api_base} timed out while connecting."
        
    except requests.exceptions.ReadTimeout:
        print(f"DEBUG API: Read timeout after {time.time() - start_time:.2f} seconds")
        return f"Read timeout: The request to {api_base} timed out while waiting for response."
        
    except requests.exceptions.ConnectionError as e:
        print(f"DEBUG API: Connection error: {str(e)}")
        return f"Connection error: Cannot connect to {api_base}. Please check if the Finance Chat API server is running."
        
    except Exception as e:
        print(f"DEBUG API: Unexpected error: {str(e)}")
        return f"Unexpected error: {str(e)}"

async def send_api_request(api_type, api_base, api_key, message, **kwargs):
    """Route the request to the appropriate API based on type."""
    if api_type == "openai":
        return await send_openai_api_request(api_base, api_key, message)
    else:
        # For finance chat API, call the synchronous function in a way that doesn't block
        loop = asyncio.get_event_loop()
        system_prompt = kwargs.get("system_prompt", "")
        model = kwargs.get("model", "gpt-4")
        use_rag = kwargs.get("use_rag", True)
        namespace = kwargs.get("namespace", "sp500-qa-demo")
        
        # Run the synchronous requests call in a thread pool
        return await loop.run_in_executor(
            None,
            lambda: send_finance_chat_sync(api_base, message, system_prompt, model, use_rag, namespace)
        )

async def send_openai_chat_sync(api_base: str, api_key: str, prompt: str, model: str = "gpt-4") -> str:
    """Send a request to the OpenAI API and return the response."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.7
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(api_base, headers=headers, json=payload) as response:
            if response.status == 200:
                data = await response.json()
                return data["choices"][0]["message"]["content"]
            else:
                return f"Error: {response.status} - {await response.text()}"