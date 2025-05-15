import json

def persist_chat_history(project_id, messages):
    """Save the chat history to a JSON file."""
    filename = f"chat_history_{project_id}.json"
    with open(filename, "w") as f:
        json.dump(messages, f, indent=2) 