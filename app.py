import streamlit as st
import json
import os
import uuid
import asyncio
import aiohttp
import time
from datetime import datetime
import random

# Import our modules
from attacks import load_attacks_from_json, get_default_prompts
from storage import persist_chat_history
from worker import (
    message_queue, 
    start_worker_thread, 
    stop_worker_thread, 
    queue_attack_iteration, 
    check_for_results
)

st.set_page_config(page_title="Agent Smith", layout="wide")

# Title and description
st.title("Agent Smith")
st.markdown("An adversarial testing loop for OpenAI-compatible chat APIs")

# Define functions before they are called
def load_attacks_from_json(file_path="attacks.json"):
    """Load attacks from the attacks.json file and convert to a flat list of prompts."""
    try:
        if os.path.exists(file_path):
            with open(file_path, "r") as f:
                attacks_data = json.load(f)
            
            # Convert nested structure to flat list of prompts
            prompts = []
            for category, category_data in attacks_data.items():
                for key, value in category_data.items():
                    if key != "Objective":  # Skip the objective descriptions
                        prompts.append(value)
            
            return prompts
        else:
            st.warning(f"File {file_path} not found. Using default prompts.")
            return None
    except Exception as e:
        st.error(f"Error loading attacks from {file_path}: {str(e)}")
        return None

# Initialize session state variables if they don't exist
if "messages" not in st.session_state:
    st.session_state.messages = []
if "attack_running" not in st.session_state:
    st.session_state.attack_running = False
if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = ""
if "iteration_count" not in st.session_state:
    st.session_state.iteration_count = 0
if "prompts" not in st.session_state:
    # Default prompts as fallback
    st.session_state.prompts = get_default_prompts()
if "api_type" not in st.session_state:
    st.session_state.api_type = "openai"
if "worker_thread" not in st.session_state:
    st.session_state.worker_thread = None
if "processing" not in st.session_state:
    st.session_state.processing = False
if "processing_start_time" not in st.session_state:
    st.session_state.processing_start_time = None
if "last_check_time" not in st.session_state:
    st.session_state.last_check_time = time.time()

# Try to load attacks from attacks.json at startup
attacks = load_attacks_from_json("attacks.json")
if attacks:
    st.session_state.prompts = attacks

# Sidebar with configuration options
with st.sidebar:
    st.header("API Configuration")
    
    # Add API type selector
    api_type = st.selectbox(
        "Select API to Test",
        options=["openai", "finance-chat"],
        index=0,
        format_func=lambda x: "OpenAI API" if x == "openai" else "Finance Chat API",
        help="Select which API endpoint to test"
    )
    st.session_state.api_type = api_type
    
    if api_type == "openai":
        # Standard OpenAI-compatible API settings
        api_base = st.text_input(
            "API Base URL", 
            value="https://api.openai.com/v1/chat/completions",
            help="The base URL for the OpenAI-compatible API"
        )
        
        api_key = st.text_input(
            "API Key", 
            type="password",
            help="Your API key for authentication"
        )
    else:
        # Finance Chat API settings
        api_base = st.text_input(
            "Finance Chat API URL", 
            value="http://localhost:5726/api/chat",
            help="The URL for the Finance Chat API endpoint"
        )
        
        api_key = st.text_input(
            "API Key (if required)", 
            type="password",
            help="API key (if required for the Finance Chat API)"
        )
        
        # Finance Chat specific settings
        st.subheader("Finance Chat Settings")
        
        # Add system prompt option
        system_prompt = st.text_area(
            "System Prompt",
            value="""You are a stock market analyst and trading assistant. You help users analyze stocks and execute trades.""",
            help="System prompt for the Finance Chat API"
        )
        
        # Add namespace option
        namespace = st.text_input(
            "Namespace",
            value="sp500-qa-demo",
            help="Namespace for RAG queries"
        )
        
        # Add model selection
        model = st.selectbox(
            "Model",
            options=["gpt-4", "gpt-3.5-turbo"],
            index=0,
            help="Language model to use"
        )
        
        # RAG toggle
        use_rag = st.checkbox("Use RAG", value=True, help="Enable RAG for queries")
    
    # Project ID (common to both API types)
    project_id = st.text_input(
        "Project ID", 
        help="Unique identifier for this testing session"
    )
    
    st.divider()
    
    # Prompt configuration section
    st.header("Adversarial Prompts")
    
    # File uploader for JSON prompts
    uploaded_file = st.file_uploader("Upload JSON prompts file", type=["json"])
    
    if uploaded_file is not None:
        try:
            # Load prompts from the uploaded JSON file
            prompt_data = json.load(uploaded_file)
            
            if isinstance(prompt_data, list) and all(isinstance(item, str) for item in prompt_data):
                st.session_state.prompts = prompt_data
                st.success(f"Loaded {len(prompt_data)} prompts from file")
            else:
                st.error("Invalid JSON format. File must contain an array of strings.")
        except Exception as e:
            st.error(f"Error loading prompts: {str(e)}")
    
    # Show a sample of loaded prompts
    with st.expander("View loaded prompts", expanded=False):
        for i, prompt in enumerate(st.session_state.prompts[:3]):
            st.text(f"{i+1}. {prompt[:50]}..." if len(prompt) > 50 else f"{i+1}. {prompt}")
        
        if len(st.session_state.prompts) > 3:
            st.text(f"... and {len(st.session_state.prompts) - 3} more")
    
    # Try to load from attacks.json if it exists and no file was uploaded
    if uploaded_file is None:
        attacks = load_attacks_from_json("attacks.json")
        if attacks:
            st.session_state.prompts = attacks
            st.success(f"Loaded {len(attacks)} prompts from attacks.json")
    
    st.divider()
    
    # Attack control button
    if not st.session_state.attack_running:
        if st.button("Start Attack"):
            if (api_type == "openai" and not api_key):
                st.error("API Key is required")
            elif not project_id:
                st.error("Project ID is required")
            else:
                # Start the background worker if not already running
                if st.session_state.worker_thread is None:
                    worker_thread = start_worker_thread()
                    st.session_state.worker_thread = worker_thread
                
                st.session_state.attack_running = True
                st.session_state.current_project_id = project_id
                st.session_state.iteration_count = 0
                st.session_state.messages = []
                st.session_state.processing = False
                
                # Store current configuration in session state
                st.session_state.api_base = api_base
                st.session_state.api_key = api_key
                if api_type == "finance-chat":
                    st.session_state.system_prompt = system_prompt
                    st.session_state.namespace = namespace
                    st.session_state.model = model
                    st.session_state.use_rag = use_rag
                
                st.rerun()
    else:
        if st.button("Stop Attack"):
            st.session_state.attack_running = False
            # Signal the worker thread to stop
            if st.session_state.worker_thread is not None:
                stop_worker_thread()
                st.session_state.worker_thread = None
            st.rerun()
    
    # Show current attack information if running
    if st.session_state.attack_running:
        st.metric("Current Project", st.session_state.current_project_id)
        st.metric("Iterations", st.session_state.iteration_count)
        st.metric("API Type", "OpenAI API" if st.session_state.api_type == "openai" else "Finance Chat API")

# Main UI - Display chat interface
chat_container = st.container()

with chat_container:
    # Display existing messages
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            with st.chat_message("assistant"):
                st.markdown(msg["content"])
                if "metrics" in msg:
                    metrics = msg["metrics"]
                    with st.expander("Response Metrics", expanded=True):
                        col1, col2 = st.columns([1, 4])
                        with col1:
                            st.metric("Score", f"{metrics['score']:.1f}/10.0")
                        with col2:
                            st.markdown(f"**Reasoning:** {metrics['reasoning']}")

    # If attack is running, show status
    if st.session_state.attack_running:
        # Show processing message if we're currently processing a request
        if st.session_state.processing:
            with st.chat_message("assistant"):
                st.markdown("Processing... generating response...")
                
                # Check for timeout
                current_time = time.time()
                if st.session_state.processing_start_time and (current_time - st.session_state.processing_start_time > 30):
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": "Processing timed out. Retrying with a simpler approach.",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.processing = False
                    st.session_state.processing_start_time = None
                    st.rerun()
                    
                # Use a more direct approach that doesn't rely on worker threads
                try:
                    # Import here to avoid circular imports
                    from api import send_finance_chat_sync
                    from attacks import start_attack
                    from metrics import get_metrics_and_reasoning
                    
                    # Generate adversarial prompt
                    prompt = start_attack(st.session_state.prompts, st.session_state.iteration_count)
                    
                    # Call the API directly without worker thread
                    if st.session_state.api_type == "finance-chat":
                        response = send_finance_chat_sync(
                            st.session_state.api_base,
                            prompt,
                            st.session_state.system_prompt,
                            st.session_state.model,
                            st.session_state.use_rag,
                            st.session_state.namespace
                        )
                    else:
                        # Not implemented yet
                        response = "Error: Direct OpenAI API calls not implemented yet."
                    
                    # Calculate metrics
                    metrics = get_metrics_and_reasoning(response)
                    
                    # Add the prompt to messages
                    st.session_state.messages.append({
                        "role": "user",
                        "content": prompt,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Add the response to messages
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": response,
                        "metrics": metrics,
                        "timestamp": datetime.now().isoformat()
                    })
                    
                    # Persist chat history
                    persist_chat_history(st.session_state.current_project_id, st.session_state.messages)
                    
                    # Increment iteration count
                    st.session_state.iteration_count += 1
                    
                    # Reset processing flag
                    st.session_state.processing = False
                    st.session_state.processing_start_time = None
                    
                    # Rerun to update the UI
                    st.rerun()
                except Exception as e:
                    # Handle errors
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": f"Error: {str(e)}",
                        "timestamp": datetime.now().isoformat()
                    })
                    st.session_state.processing = False
                    st.session_state.processing_start_time = None
                    st.rerun()
        else:
            # Show "generating next prompt" message if we're ready for the next iteration
            with st.chat_message("user"):
                st.markdown("Generating a new adversarial prompt...")
                
                # Start a new iteration if we're not currently processing
                if st.session_state.attack_running and not st.session_state.processing:
                    st.session_state.processing = True
                    st.session_state.processing_start_time = time.time()
                    
                    # We're using a direct approach now rather than worker threads
                    # Just rerun to trigger the processing code above
                    st.rerun()
