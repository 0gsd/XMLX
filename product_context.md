# XMlX.app Product Context & Requirements

## Core Purpose
**XMlX.app** is a manufacturing tool for the **XMLX Audio Standard**.
It allows users to generate or process audio (using AI tools like MusicGen, Demucs, etc.) and package the results into a structured **XML fileset**.

## The XMLX Standard
- **Format**: A proprietary XML structure (reference: `xmlx<ver>eg.xml`).
- **Goal**: To be consumed by specialized "MP3 Player" style applications that read this XML format.
- **Components**:
  - **Master Audio**: The full mix.
  - **Stems**: Separated tracks (Vocals, Bass, Drums, etc.).
  - **Metadata**: Title, Artist, BPM, etc.
  - **MIDI**: (Optional) Transcriptions of the audio.

## Key Workflows
1.  **Generation/Upload**: User creates audio via `Sonat`, `Tugue`, `Cmcmt` or uploads via `Xymix`/`15010`.
2.  **Processing**: The backend splits/renders the audio.
3.  **Persistence**: Files are stored and accessible via URL.
4.  **XML Generation**: The app generates an `.xml` file containing links to all these assets.
5.  **Distribution**: The user downloads or shares the XML file (and potential assets).

## Architecture Constraints
- **Backend**: Flask on Google Cloud Run.
- **Storage**:
  - **Legacy**: GCSFuse (Attempted to treat GCS as a filesystem, failed due to I/O consistency).
  - **Current (v4.61+)**: Ephemeral RAM (`/tmp`). Stable but non-persistent.
- **Critical Requirement**: Generated files must be downloadable to be useful.

## Persistent Memory
This document (`product_context.md`) serves as the source of truth for future AI agents to understand *why* we are building this, not just *how*.

## Technology Stack (Key Dependencies)
- **Core**: `flask`, `gunicorn`, `werkzeug`
- **Audio Processing**:
  - `demucs` (Stem Separation)
  - `librosa`, `soundfile`, `pydub` (Audio Manipulation)
  - `mido`, `midi2audio`, `midiutil`, `music21` (MIDI creation/parsing)
  - `fluidSynth` (Rendering MIDI to Audio)
- **AI/ML**:
  - `torch`, `torchaudio`, `tensorflow`, `onnxruntime`
  - `basic-pitch`, `torchcrepe`, `piano-transcription-inference` (Transcription)
  - `google-generativeai` (Gemini integration)
- **External APIs**: `roex-python`, `musicai-sdk`
