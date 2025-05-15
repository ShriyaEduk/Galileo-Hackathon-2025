import streamlit as st
import json
import os
import uuid
import time
from datetime import datetime
import random
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Import our modules
from attacks import load_attacks_from_json, get_default_prompts
from storage import persist_chat_history
from worker import (
    message_queue, 
    start_worker_thread, 
    stop_worker_thread, 
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

def display_metrics_in_expander(metrics, expander_label="Response Metrics", expanded_state=True):
    """Helper function to display metrics in an expander."""
    with st.expander(expander_label, expanded=expanded_state):
        col1, col2 = st.columns([1, 4])
        with col1:
            st.metric("Score", f"{metrics.get('score', 0.0):.1f}/10.0")
        with col2:
            st.markdown(f"**Reasoning:** {metrics.get('reasoning', 'No reasoning provided')}")

# Initialize session state variables if they don't exist
if "messages" not in st.session_state: # For persistent log
    st.session_state.messages = []
if "attack_running" not in st.session_state:
    st.session_state.attack_running = False
if "processing" not in st.session_state:
    st.session_state.processing = False

# New session state variables for granular UI updates
if "current_status_message" not in st.session_state:
    st.session_state.current_status_message = "Idle. Configure and start an attack."
if "current_prompt_content" not in st.session_state:
    st.session_state.current_prompt_content = ""
if "current_prompt_type_label" not in st.session_state: # e.g. "Base Prompt" or "Variation #X"
    st.session_state.current_prompt_type_label = ""
if "current_response_content" not in st.session_state:
    st.session_state.current_response_content = ""
if "current_metrics_content" not in st.session_state: # Store the dict
    st.session_state.current_metrics_content = {}
if "current_base_prompt_summary" not in st.session_state: # Dict keyed by base_prompt_index
    st.session_state.current_base_prompt_summary = {} 
if "overall_summary_message" not in st.session_state: # For "ALL_CYCLES_COMPLETE"
    st.session_state.overall_summary_message = ""


if "current_project_id" not in st.session_state:
    st.session_state.current_project_id = ""
if "prompts" not in st.session_state:
    # Default prompts as fallback
    st.session_state.prompts = get_default_prompts()
if "api_type" not in st.session_state:
    st.session_state.api_type = "openai"
if "worker_thread" not in st.session_state:
    st.session_state.worker_thread = None
# if "processing_start_time" not in st.session_state: # May not be needed with this model
#     st.session_state.processing_start_time = None
# if "last_check_time" not in st.session_state: # May not be needed
#     st.session_state.last_check_time = time.time()


# Try to load attacks from attacks.json at startup
attacks_json_file = "attacks.json" # Define to avoid magic string
loaded_attacks = load_attacks_from_json(attacks_json_file)
if loaded_attacks:
    st.session_state.prompts = loaded_attacks

# Sidebar with configuration options
with st.sidebar:
    st.header("API Configuration")
    
    api_type_options = ["openai", "finance-chat"]
    api_type_selected = st.selectbox(
        "Select API to Test",
        options=api_type_options,
        index=api_type_options.index(st.session_state.api_type) if st.session_state.api_type in api_type_options else 0,
        format_func=lambda x: "OpenAI API" if x == "openai" else "Finance Chat API",
        help="Select which API endpoint to test"
    )
    st.session_state.api_type = api_type_selected # Ensure session state is updated
    
    openai_api_key_input = st.text_input(
        "OpenAI API Key (for prompt improvement)",
        type="password",
        key="openai_api_key_for_improvement_input", 
        help="Your OpenAI API key, used for generating improved prompts with GPT-3.5-turbo."
    )
    
    # API specific settings
    api_base_value = "https://api.openai.com/v1/chat/completions" if st.session_state.api_type == "openai" else "http://localhost:5726/api/chat"
    api_base_label = "API Base URL" if st.session_state.api_type == "openai" else "Finance Chat API URL"
    api_base = st.text_input(api_base_label, value=api_base_value)
    
    api_key_label = "API Key" if st.session_state.api_type == "openai" else "API Key (if required)"
    api_key = st.text_input(api_key_label, type="password", key="target_api_key_input")

    system_prompt_value = ""
    namespace_value = ""
    model_value = "gpt-4" # Default for openai
    use_rag_value = True

    if st.session_state.api_type == "finance-chat":
        st.subheader("Finance Chat Settings")
        system_prompt_value = st.text_area(
            "System Prompt",
            value="""You are a stock market analyst and trading assistant. You help users analyze stocks and execute trades.""",
            help="System prompt for the Finance Chat API"
        )
        namespace_value = st.text_input(
            "Namespace", value="sp500-qa-demo", help="Namespace for RAG queries"
        )
        model_value = st.selectbox(
            "Model", options=["gpt-4", "gpt-3.5-turbo"], index=0, help="Language model to use"
        )
        use_rag_value = st.checkbox("Use RAG", value=True, help="Enable RAG for queries")
    elif st.session_state.api_type == "openai":
        model_value = st.selectbox( # Allow model selection for OpenAI too
            "Model (for target API)", options=["gpt-4", "gpt-3.5-turbo", "gpt-4-turbo"], index=0, help="Language model for the target API"
        )


    project_id_value = st.text_input(
        "Project ID", 
        value=st.session_state.current_project_id,
        help="Unique identifier for this testing session"
    )
    
    st.divider()
    st.header("Adversarial Prompts")
    uploaded_file = st.file_uploader("Upload JSON prompts file", type=["json"])
    
    if uploaded_file is not None:
        try:
            prompt_data = json.load(uploaded_file)
            if isinstance(prompt_data, list) and all(isinstance(item, str) for item in prompt_data):
                st.session_state.prompts = prompt_data
                st.success(f"Loaded {len(prompt_data)} prompts from file")
            else:
                st.error("Invalid JSON format. File must contain an array of strings.")
        except Exception as e:
            st.error(f"Error loading prompts: {str(e)}")
    elif not loaded_attacks: # if attacks.json didn't load and no file uploaded
        st.info(f"Default prompts loaded. Create '{attacks_json_file}' or upload a file to customize.")


    with st.expander("View loaded prompts", expanded=False):
        for i, prompt_text_item in enumerate(st.session_state.prompts[:5]): # Show up to 5
            st.text(f"{i+1}. {prompt_text_item[:70]}..." if len(prompt_text_item) > 70 else f"{i+1}. {prompt_text_item}")
        if len(st.session_state.prompts) > 5:
            st.text(f"... and {len(st.session_state.prompts) - 5} more")
    
    st.divider()
    
    if not st.session_state.attack_running:
        if st.button("Start Attack", key="start_attack_button"):
            valid_input = True
            if not openai_api_key_input: # Check the variable holding UI input
                st.error("OpenAI API Key (for prompt improvement) is required.")
                valid_input = False
            if not project_id_value:
                st.error("Project ID is required.")
                valid_input = False
            if not api_key: # Check target API key
                st.error("Target API Key is required.")
                valid_input = False
            
            if valid_input:
                if st.session_state.worker_thread is None or not st.session_state.worker_thread.is_alive():
                    st.session_state.worker_thread = start_worker_thread()
                
                st.session_state.attack_running = True
                st.session_state.processing = True
                st.session_state.current_project_id = project_id_value
                st.session_state.messages = [] # Reset persistent log
                st.session_state.current_base_prompt_summary = {} # Reset summaries
                st.session_state.overall_summary_message = ""
                st.session_state.current_status_message = "🚀 Attack initiated..."
                st.session_state.current_prompt_content = ""
                st.session_state.current_response_content = ""
                st.session_state.current_metrics_content = {}


                worker_params = {
                    "api_type": st.session_state.api_type,
                    "api_base": api_base,
                    "api_key": api_key, # Target API key
                    "prompts": st.session_state.prompts,
                    "kwargs": { 
                        "openai_api_key": openai_api_key_input, # For prompt improvement
                        "system_prompt": system_prompt_value if st.session_state.api_type == "finance-chat" else None,
                        "model": model_value, # Model for the target API
                        "use_rag": use_rag_value if st.session_state.api_type == "finance-chat" else None,
                        "namespace": namespace_value if st.session_state.api_type == "finance-chat" else None,
                    }
                }
                print(f"DEBUG APP: Queuing START_FULL_ATTACK_CYCLE with openai_api_key: {'SET' if openai_api_key_input else 'NOT SET'}")
                message_queue.put({"action": "START_FULL_ATTACK_CYCLE", "params": worker_params})
                st.rerun()
    else:
        if st.button("Stop Attack"):
            st.session_state.attack_running = False
            st.session_state.processing = False # Stop processing on UI side
            if st.session_state.worker_thread is not None and st.session_state.worker_thread.is_alive():
                stop_worker_thread() # Signal worker to stop
                # st.session_state.worker_thread = None # Worker will terminate itself
            st.session_state.current_status_message = "🛑 Attack stopped by user."
            st.rerun()
    
    if st.session_state.attack_running:
        st.metric("Current Project", st.session_state.current_project_id)

# --- Message Processing Logic ---
if st.session_state.get('attack_running') and st.session_state.get('processing'):
    worker_message = check_for_results()
    if worker_message:
        action = worker_message.get("action")
        print(f"DEBUG UI: === PROCESSING ACTION: {action} ===")

        # Reset/clear parts of the display state for new phases
        if action == "NEW_BASE_PROMPT":
            st.session_state.current_prompt_content = ""
            st.session_state.current_response_content = ""
            st.session_state.current_metrics_content = {}

        # Update state based on action
        if action == "NEW_BASE_PROMPT":
            bp_idx = worker_message.get("base_prompt_index", -1)
            bp_content = worker_message.get("base_prompt_content", "Error: Content missing.")
            st.session_state.current_status_message = f"🎯 Starting new base prompt #{bp_idx + 1}: {bp_content[:80]}..."
            st.session_state.messages.append({
                "role": "system", 
                "content": f"🎯 Starting Base Prompt #{bp_idx+1}: {bp_content}",
                "timestamp": datetime.now().isoformat()
            })
        elif action == "PROMPT_GENERATING":
            bp_idx = worker_message.get("base_prompt_index", -1)
            var_idx = worker_message.get("variation_count", 0)
            st.session_state.current_status_message = f"⏳ Generating prompt variation #{var_idx + 1} for Base Prompt #{bp_idx + 1}..."
            st.session_state.current_prompt_type_label = f"Variation #{var_idx + 1} (Base #{bp_idx + 1})"
            st.session_state.current_prompt_content = "_Waiting for AI to generate prompt..._"
            st.session_state.current_response_content = "" 
            st.session_state.current_metrics_content = {}   
        elif action == "PROMPT_GENERATED":
            prompt_text = worker_message.get("prompt", "Error: Prompt text missing.")
            is_base = worker_message.get("is_base_prompt", False)
            bp_idx = worker_message.get("base_prompt_index", -1)
            var_idx = worker_message.get("variation_count", 0)
            type_label = "Base Prompt" if is_base else f"Generated Variation #{var_idx + 1}"
            st.session_state.current_status_message = f"✅ {type_label} (Base #{bp_idx+1}) ready for testing."
            st.session_state.current_prompt_type_label = f"{type_label} (Base #{bp_idx+1})"
            st.session_state.current_prompt_content = prompt_text
        elif action == "TESTING_PROMPT":
            prompt_being_tested = worker_message.get("prompt_being_tested", "Error: Prompt missing.")
            bp_idx = worker_message.get("base_prompt_index", -1)
            var_idx = worker_message.get("variation_count", 0)
            st.session_state.current_status_message = f"🧪 Testing prompt (Variation #{var_idx + 1} of Base #{bp_idx + 1})..."
            st.session_state.current_response_content = "_Waiting for target API response..._"
            st.session_state.current_metrics_content = {}
            st.session_state.messages.append({
                "role": "user", 
                "content": f"[Testing V{var_idx+1}/B{bp_idx+1}]:\\n{prompt_being_tested}",
                "timestamp": datetime.now().isoformat(),
                "iteration_id": worker_message.get("iteration_id")
            })
        elif action == "RESPONSE_RECEIVED":
            response_text = worker_message.get("response", "Error: Response text missing.")
            metrics = worker_message.get("metrics", {})
            prompt_text = worker_message.get("prompt", "N/A") 
            bp_idx = worker_message.get("base_prompt_index", -1)
            var_idx = worker_message.get("variation_count", 0)
            st.session_state.current_status_message = f"📊 Response received for Variation #{var_idx + 1} of Base #{bp_idx + 1}."
            st.session_state.current_response_content = response_text
            st.session_state.current_metrics_content = metrics
            st.session_state.messages.append({
                "role": "assistant", 
                "content": response_text,
                "metrics": metrics,
                "timestamp": datetime.now().isoformat(),
                "iteration_id": worker_message.get("iteration_id"),
                "associated_prompt": prompt_text 
            })
            persist_chat_history(st.session_state.current_project_id, st.session_state.messages)
        elif action == "ITERATION_VARIATION_COMPLETE":
            bp_idx = worker_message.get("base_prompt_index", -1)
            var_idx = worker_message.get("variation_count", 0)
            if var_idx < 14: 
                st.session_state.current_status_message = f"➡️ Variation #{var_idx + 1} complete. Preparing for variation #{var_idx + 2} of Base #{bp_idx + 1}..."
            else:
                st.session_state.current_status_message = f"🏁 All 15 variations for Base Prompt #{bp_idx + 1} complete. Summarizing..."
        elif action == "BASE_PROMPT_CYCLE_COMPLETE":
            bp_idx = worker_message.get("base_prompt_index", -1)
            summary_scores = worker_message.get("summary_scores", [])
            base_prompt_content = worker_message.get("base_prompt_content", "")
            full_chain = worker_message.get("full_chain_details", [])
            st.session_state.current_base_prompt_summary[bp_idx] = {
                "index": bp_idx, "content": base_prompt_content,
                "scores": summary_scores, "full_chain_details": full_chain
            }
            st.session_state.current_status_message = f"Base Prompt #{bp_idx + 1} cycle complete. Scores: {summary_scores}"
            st.session_state.messages.append({
                "role": "system",
                "content": f"🏁 Base Prompt #{bp_idx+1} Cycle Complete. Original: '{base_prompt_content[:60]}...'. Scores: {summary_scores}",
                "timestamp": datetime.now().isoformat()
            })
            persist_chat_history(st.session_state.current_project_id, st.session_state.messages)
            st.session_state.current_prompt_content = "" # Clear last variation details
            st.session_state.current_response_content = ""
            st.session_state.current_metrics_content = {}
        elif action == "ALL_CYCLES_COMPLETE":
            st.session_state.overall_summary_message = "🎉 All attack cycles completed!"
            st.session_state.current_status_message = st.session_state.overall_summary_message
            st.session_state.processing = False
            # st.session_state.attack_running = False # Keep running to show results
            st.session_state.messages.append({
                "role": "system", "content": st.session_state.overall_summary_message,
                "timestamp": datetime.now().isoformat()
            })
            persist_chat_history(st.session_state.current_project_id, st.session_state.messages)
        elif action == "ERROR_OCCURRED":
            error_message = worker_message.get("message", "An unknown error occurred in the worker.")
            stage = worker_message.get("stage", "unknown stage")
            iter_id = worker_message.get("iteration_id", "N/A")
            full_error_msg = f"🛑 ERROR (Iter: {iter_id}, Stage: {stage}): {error_message}"
            st.session_state.current_status_message = full_error_msg
            st.session_state.overall_summary_message = full_error_msg 
            st.session_state.processing = False
            st.session_state.messages.append({
                "role": "error", "content": full_error_msg,
                "timestamp": datetime.now().isoformat()
            })
            persist_chat_history(st.session_state.current_project_id, st.session_state.messages)
        
        st.rerun() # Simplified: if we processed a message, we almost always want to show its effects.

    elif st.session_state.get('processing'): # No message, but still processing
        time.sleep(0.25) # Polling interval
        if st.session_state.get('processing'): # Check again after sleep; processing might have been set to False by a concurrently processed message.
             st.rerun()

# --- UI Rendering Section ---
st.header("Live Attack Progress")

if st.session_state.attack_running or st.session_state.overall_summary_message: # Show even if attack just finished
    # Display current status
    if "error" in st.session_state.current_status_message.lower():
        st.error(st.session_state.current_status_message)
    elif "complete" in st.session_state.current_status_message.lower() or \
         "🎉" in st.session_state.current_status_message:
        st.success(st.session_state.current_status_message)
    else:
        st.info(st.session_state.current_status_message)

    # Display current prompt being processed
    if st.session_state.current_prompt_content:
        st.markdown(f"**{st.session_state.current_prompt_type_label}:**")
        st.code(st.session_state.current_prompt_content, language="text")

    # Display current response
    if st.session_state.current_response_content and \
       st.session_state.current_response_content != "_Waiting for target API response..._":
        st.markdown("**Target API Response:**")
        st.code(st.session_state.current_response_content, language="text")
    
    # Display current metrics
    if st.session_state.current_metrics_content:
        display_metrics_in_expander(st.session_state.current_metrics_content, "Current Iteration Metrics")

    # Display summaries for completed base prompts
    if st.session_state.current_base_prompt_summary:
        st.subheader("Base Prompt Summaries")
        sorted_summaries = sorted(st.session_state.current_base_prompt_summary.items())
        for bp_idx, summary_data in sorted_summaries:
            with st.expander(f"Summary for Base Prompt #{summary_data.get('index', bp_idx) + 1}", expanded=False):
                st.write(f"Original: {summary_data.get('content', 'N/A')[:100]}...")
                st.write(f"Scores from 15 variations: {summary_data.get('scores', [])}")
                # Optionally, display full_chain_details if needed

    if st.session_state.overall_summary_message and not st.session_state.processing :
        if "error" in st.session_state.overall_summary_message.lower():
             st.error(f"Overall Status: {st.session_state.overall_summary_message}")
        else:
             st.success(f"Overall Status: {st.session_state.overall_summary_message}")
else:
    st.info("Configure the attack parameters in the sidebar and click 'Start Attack'.")


# --- Persistent Chat Log Rendering ---
st.header("Full Attack Log")
chat_container = st.container()
with chat_container:
    if not st.session_state.messages:
        st.caption("Attack log will appear here...")

    for msg in st.session_state.messages:
        role = msg.get("role", "system") # Default to system if role is missing
        content = msg.get("content", "")
        
        if role == "error":
            with st.chat_message("assistant", avatar="⚠️"): # Using assistant avatar for errors for now
                st.error(content)
        elif role == "system":
             with st.chat_message("assistant", avatar="⚙️"): # System message
                st.info(content)
        elif role == "user": # Prompts sent to target API
            with st.chat_message("user"):
                st.markdown(content)
        elif role == "assistant": # Responses from target API
            with st.chat_message("assistant"):
                st.markdown(content)
                if "metrics" in msg: # Ensure metrics exist
                    display_metrics_in_expander(msg["metrics"], "Response Metrics", expanded_state=False)
        else: # Fallback for unknown roles
            with st.chat_message(role):
                st.markdown(content)
