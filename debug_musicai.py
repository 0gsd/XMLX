import musicai_sdk
import os

# --- Secure Config ---
# NEVER commit API keys to git. Use os.environ.
API_KEY = os.environ.get("MUSICAI_API_KEY") or "MISSING_KEY"

def list_workflows():
    print(f"--- Authenticating with Music.AI ---", flush=True)
    try:
        client = musicai_sdk.MusicAiClient(api_key=API_KEY)
    except AttributeError:
        # Maybe the class is different? Let's inspect.
        print(f"[DEBUG] musicai_sdk contents: {dir(musicai_sdk)}", flush=True)
        # Try finding a client class
        possible_clients = [x for x in dir(musicai_sdk) if 'Client' in x]
        if possible_clients:
             print(f"[DEBUG] Found potential clients: {possible_clients}", flush=True)
             cls_name = possible_clients[0]
             client = getattr(musicai_sdk, cls_name)(api_key=API_KEY)
        else:
             print("[!] Could not initialize client.", flush=True)
             return

    print(f"--- Listing Workflows ---", flush=True)
    try:
        # Correct method identified from introspection
        if hasattr(client, 'list_workflows'):
             workflows = client.list_workflows()
        else:
             print(f"[DEBUG] Client dir: {dir(client)}")
             return

        print(f"Workflow container type: {type(workflows)}", flush=True)

        if isinstance(workflows, dict):
             print(f"Keys: {list(workflows.keys())}", flush=True)
             # Maybe the list is under a key locally?
             if 'files' in workflows: # Standard MusicAI?
                  items = workflows['files']
             elif 'workflows' in workflows:
                  items = workflows['workflows']
             elif 'results' in workflows:
                  items = workflows['results']
             else:
                  # Maybe dict of ID -> Obj
                  items = list(workflows.values())
        else:
             items = workflows

        print(f"Found {len(items)} items.", flush=True)
        if items:
            print(f"First Item: {items[0]}", flush=True)

        for w in items:
             print(f" - {w}", flush=True)

    except Exception as e:
        print(f"[!] Error listing workflows: {e}", flush=True)
        # Full traceback?
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    list_workflows()
