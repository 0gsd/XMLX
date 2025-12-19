# Status Context: 09-Dec-2025

**Time:** 16:00 EST
**Objective:** v1.1 Refactor (GPU Support) + XML0X Module Preview

## 1. Cloud Run Deployment (v1.1)
**Status:** In Progress (Build Running)

### Critical Fixes Applied (Check these if build fails):
1.  **Dockerfile**:
    *   Base Image: `pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime` (Huge image).
    *   Missing Tool: Added `wget` to `apt-get install` (Required for piano model).
    *   Interactive Prompt: Added `ENV DEBIAN_FRONTEND=noninteractive` (Fixes `tzdata` hang).
2.  **deploy_gcp.sh**:
    *   **Timeout**: Split into 2 steps. Step 1 (`gcloud builds submit`) now has `--timeout=2h` to accommodate the large CUDA image.
    *   **Region**: Added `--region $REGION` to build step to prevent CLI prompts.
    *   **Resources**: Deploy step sets `--memory 16Gi` and `--cpu 4` (Required for Nvidia L4 GPU).

## 2. Codebase Status
*   **GPU Logic**: All python scripts (`p2mix1.py`, `15010.py`, etc.) updated to use `device = 'cuda' if torch.cuda.is_available() else 'cpu'`.
*   **15010 Module**: Added "Favorite Instrument" UI and logic. Verification needed on new deployment.

## 3. New Module: XML0X (Aux Player)
**Status:** Partial Implementation (Local Only)
*   **Design**: Approved (`design_xml0x.md`).
*   **Implemented**:
    *   `xml0x.py` (Backend Stub).
    *   `main.py` (Route `/xml0x` registered).
    *   `templates/xml0x.html` (UI Skeleton - Dark Mode/Winamp Style).
    *   `static/js/xmlynth.js` (Synth Engine saved).
*   **Pending**:
    *   `xmlx_player_engine.js` (The actual logic to parse XMLX and play audio/midi).
    *   Wiring up the UI buttons to the JS engine.

## 4. Next Steps
1.  **Verify Deployment**:
    *   Confirm GPU usage in logs.
    *   Test `15010` generic functionality.
    *   Test "Favorite Instrument" feature.
2.  **Finish XML0X**:
    *   Implement the JS player logic locally.
    *   Test local playback.
3.  **Next Deploy**:
    *   Will include the XML0X player.
    *   Should be faster (cached layers).
