# Standard Development Workflow

**Effective Date**: 2025-12-11
**Context**: All new audio processing modules (e.g., MusicAI integrations).

## The Protocol

1.  **Local Python First**
    *   Create `[module_name].py` in `tools/musicgen/p2mix/`.
    *   Implement core logic (args, processing, API calls).
    *   **Do not** touch `unified_index.html` or `main.py` yet.

2.  **Local Verification**
    *   Run locally: `python3 [module_name].py input.wav output_dir [args]`
    *   Iterate until logic is rock solid.

3.  **UI & Integration (The "Push")**
    *   Once the script is approved:
        *   Design the Module Page in `unified_index.html` (Unique Color Palette).
        *   Add Route/Handler in `main.py`.
    *   Deploy to GCP.

## Key Resources
*   **RoEx/MusicAI Keys**: Hardcoded in scripts for local ease (until further notice).
*   **Local Run Guide**: See `ref/local_run.md`.
