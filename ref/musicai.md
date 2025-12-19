# MusicAI SDK & API Reference

**PyPI**: [musicai-sdk](https://pypi.org/project/musicai-sdk/)
**API Docs**: [Reference](https://music.ai/docs/api/reference/)
**API Key**: `0b8c5b07-182e-4e47-a97d-34d023203a91`


## Workflow IDs (Discovered)

| Name | Slug | ID |
| :--- | :--- | :--- |
| **Separation (1In-6Stems)** | `1in-6stems` | `2843c7f0-49fd-4d96-8776-48fb1ecf80c6` |
| **Mixing (6In-1WAV)** | `6in-1wav` (approx) | `5a5e046f-4846-4c09-af34-c6e02bffeb5f` |

## Standard Workflow

The typical lifecycle for processing audio with Music.AI is:

1.  **Retrieve Workflow ID**: Fetch available workflows to find the one you need (e.g., vocal removal, stem separation).
2.  **Upload File**: Get a signed upload URL and upload your audio file.
3.  **Create Job**: Submit a job linking your uploaded file to the chosen workflow.
4.  **Poll Status**: Check the job status until it is `SUCCEEDED`.
5.  **Retrieve Results**: Get the output URLs from the completed job.

## Python SDK Usage

*Note: This is inferred from standard patterns and API structure. Verify exact method names with `dir(musicai_sdk)`.*

```python
import musicai_sdk
import time

# Configuration
API_KEY = "0b8c5b07-182e-4e47-a97d-34d023203a91"
client = musicai_sdk.MusicAiClient(api_key=API_KEY)

def process_track(input_path, workflow_name="stem-separation"):
    # 1. Get Workflow
    workflows = client.get_workflows() 
    # Logic to find workflow_id by name...
    workflow_id = "..." 

    # 2. Upload
    print(f"Uploading {input_path}...")
    upload_url = client.upload.get_signed_url() # or client.files.upload(input_path)
    # Perform upload...

    # 3. Create Job
    job = client.jobs.create(
        name=f"Process {input_path}",
        workflow=workflow_id,
        params={"inputUrl": "..."}
    )
    print(f"Job started: {job.id}")

    # 4. Poll
    while True:
        status = client.jobs.get(job.id)
        if status.status == 'SUCCEEDED':
            break
        elif status.status == 'FAILED':
            raise Exception("Job Failed")
        time.sleep(5)
    
    # 5. Results
    return status.outputs
```

## detailed API Reference

### 1. Workflows
**GET** `/workflow`
- **Purpose**: List available audio processing pipelines.
- **Response**: List of objects containing `id`, `name`, `slug`, `description`.

### 2. Uploads
**GET** `/upload`
- **Purpose**: Get a pre-signed URL for direct file upload.
- **Use Case**: Securely sending user audio to Music.AI storage before processing.

### 3. Jobs
**POST** `/job`
- **Purpose**: Start a processing task.
- **Parameters**:
    - `name` (string): Label for the job.
    - `workflow` (string): The UUID of the workflow to run.
    - `params` (object): Workflow-specific parameters (e.g., `{"inputUrl": "..."}`).
    - `metadata` (object): Custom tags.

**GET** `/job/:id`
- **Purpose**: Get job details and output.
- **Response**: Status (`SUCCEEDED`, `FAILED`, `RUNNING`) and `outputs` (results).

**GET** `/job/:id/status`
- **Purpose**: Lightweight status check.

## Environment Setup
## capabilities & Modules

Music.AI is modular. You construct "Workflows" (pipelines) in their Dashboard or Orchestrator, which then provide a Workflow ID to use in the API.

### 1. Source Separation (Stem Extraction)
*   **Function**: Splits a full mix into individual stems (Vocals, Drums, Bass, Other, Guitar, Piano).
*   **Standard Modules**:
    *   `music-ai/stems-vocals-accompaniment`: Basic 2-stem split.
    *   `music-ai/stems-instruments`: Advanced multi-stem separation (similar to Demucs/RoEx).
    *   **Features**: Mute specific instruments, isolate vocals.

### 2. AI Mastering
*   **Function**: Automated mastering of a stereo mix or stems.
*   **Modules**:
    *   **Auto-Mastering**: General propose mastering.
    *   **Focus Mastering**: targeted mastering that highlights specific elements (e.g., "Bass Focus", "Vocal Focus").

### 3. Mixing / Remixing
*   **Function**: Combining stems back into a stereo mix.
*   **Features**:
    *   **Stereo Mix Generation**: Automixing stems with genre-specific parameters.
    *   **Vocal-Focused Mix**: Automatically balances the mix to highlight vocals.

## Determining Workflow IDs

**Important**: The SDK requires a specific `workflow` UUID to run a job.

1.  **Check Available Workflows**:
    Run the following to see what workflows are active on your account:
    ```bash
    curl --request GET \
      --url https://api.music.ai/v1/workflow \
      --header 'Authorization: YOUR_API_KEY'
    ```
2.  **Dashboard Setup**:
    If the list is empty (`[]`), you must log in to the **Music.AI Dashboard** (Orchestrator).
    *   Browse the "Marketplace" or "Templates".
    *   "Clone" or "Save" the workflows you want (e.g., "Stem Separation", "Mastering").
    *   Once saved to your account, they will appear in the API list with a specific ID (e.g., `2362a51f-e9f9...`).

