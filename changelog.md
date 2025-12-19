# Changelog

## v4.74 (2025-12-19)
- Fixed P2MIX paths and removed broken soundfonts

## v4.73 (2025-12-19)
- Refactored Xymix UI to use single 128-inst selector and fixed MIDI PC injection

## v4.72 (2025-12-19)
- Key rotations

## v4.71 (2025-12-19)
- Soundfont fix for 15010

## v4.70 (2025-12-19)
- Fixes for 400 errors in xymix.py and 15010.py

## v4.67 (2025-12-18)
- Path Verification Build

## v4.66 (2025-12-18)
- XMIOX Crash Fix & v4.65 included

## v4.65 (2025-12-18)
- Robust Stitching (Sonat/Cmcmt)

## v4.63 (2025-12-18)
- Fix Tugue Crash and Sonat Silence

## v4.62 (2025-12-18)
- Fix Download Buffering via Streaming

## v4.61 (2025-12-18)
- Diagnostics

## v4.60 (2025-12-18)
- Fix: Simplified Download Handler to use robust send_from_directory (fixes Download 500s).

## v4.59 (2025-12-18)
- Fix: Created dummy input file for generative tools to prevent Orchestrator 500 crash.

## v4.58 (2025-12-18)
- Diagnosis: Enhanced Logging (Traceback + Soundfont Check) for Sonat/Tugue/Cmcmt.

## v4.57 (2025-12-18)
- Fix: Replaced Pydub Sanitizer with Copy+Chmod Sanitizer (fixes broken WAVs).

## v4.56 (2025-12-18)
- Fix: Tugue Panic Fallback crash on empty candidates.

## v4.55 (2025-12-18)
- Fix: Cmcmt Remerge (P20CO). Tugue Robust Stitching w/ Panic Fallback.

## v4.54 (2025-12-18)
- Fix: Sonat MIDI Selection. Rebuilt Fugue->Tugue, Cmcmf->Cmcmt with robust file handling.

## v4.53 (2025-12-18)
- Fix: Replaced Sonat direct import with Subprocess (matching Snata logic).

## v4.52 (2025-12-17)
- Replaced Snata with Sonat (Clean Rebuild with p2mix1-style file handling).

## v4.51 (2025-12-17)
- Fix: Applied Python-Write Sanitizer to Snata, Fugue, and CMCMF.

## v4.50 (2025-12-17)
- Fix: Snata Double-Render Python Mix (Permissions Fix).

## v4.49 (2025-12-17)
- Deprecation: Hidden FINA1 and FIMAI modules from UI.

## v4.48 (2025-12-17)
- Download Fix: Atomic Chmod 644 (No Copy) + 7px Logo.

## v4.47 (2025-12-17)
- UI Fix: Logo reduced to 7px (Retry).

## v4.46 (2025-12-17)
- Domain Awareness: Dynamic Base URL (PRO/Free) + Bare Metal Stream.

## v4.45 (2025-12-17)
- Bare Metal Stream Download (No Copy/Chmod) + 7px Logo Fix.

## v4.44 (2025-12-17)
- Download Logic Overhaul: Robust Copy + Pure Streaming (Removed FFmpeg/SendFile).

## v4.43 (2025-12-17)
- UI Polish: Compacted Logo (9px) - Retry.

## v4.42 (2025-12-17)
- UI Polish: Compacted Logo (9px). Added Verbose 404 Logging.

## v4.42 (2025-12-17)
- Added Verbose 404 Debugging for Downloads (Listing Directory Contents).

## v4.41 (2025-12-17)
- New Logo (Dots) with Full Spectrum Gradient and Centered Version.

## v4.40 (2025-12-17)
- Implemented WAV Sanitizer (ffmpeg transcode) to ensure download integrity.

## v4.39 (2025-12-17)
- Fixed Version Label (regex) & Implemented Streaming Download (Memory Safe).

## v4.38 (2025-12-17)
- Implemented Raw Response fallback for downloads (bypassing send_file).

## v4.37 (2025-12-17)
- Restored correct ASCII mask asset (v4.35 reverted it?).

## v4.36 (2025-12-17)
- Cleaned ASCII assets (removed artifacts) and finalized Overlay alignment.

## v4.35 (2025-12-17)
- Polished ASCII Overlay, Hardened Downloads (Hail Mary), and Debug Routes.

## v4.33 (2025-12-17)
- Implemented Inverse ASCII Logo Overlay (Cutout Effect)

## v4.32 (2025-12-17)
- Fix: HTTP 500 Startup Crash (Removed duplicate code in main.py). Refactor: Merged xml0x module into main.py and removed dependency.

## v4.29 (2025-12-17)
- v4.29: Fixed App Crash (Cleaned Main.py)

## v4.28 (2025-12-17)
- v4.28: Fixed Syntax Error in Main

## v4.27 (2025-12-17)
- v4.27: Added File Visibility Debug Endpoint

## v4.26 (2025-12-17)
- v4.26: Robust Download Ownership Fix with Copy-Serve

## v4.25 (2025-12-17)
- v4.25: Removed wavF Folder Dependency

## v4.24 (2025-12-17)
- v4.24: Definitive Logo Fix

## v4.23 (2025-12-17)
- v4.23: Clean Logo & Enhanced Logging

## v4.22 (2025-12-17)
- v4.22: Verbose Exception Logging for Download 500s

## v4.21 (2025-12-17)
- v4.21: Debug Logging for Snata/Cmcmf 500 Errors

## v4.20 (2025-12-17)
- v4.20: New ASCII Logo and Versioning Fix

## v4.19 (2025-12-17)
- v4.19: Fix FIMAI Layout Overflow & Download 500 Errors

## v4.18 (2025-12-17)
- v4.18: Fix Download 500 Errors (Revert to os.chmod)

## v4.17 (2025-12-16)
- v4.17: UI Polish, Permissions Fix, Fugue Rendering Fix, XMIOX Access

## v4.16 (2025-12-16)
- v4.16 UI Polish: New Logo and Layout

## v4.15 (2025-12-16)
- Fix Accordion Nav, Update ASCII Logo, Fix Syntax Errors

## v4.14 (2025-12-16)
- Final Fix v4.14: Corrected 0o644 -> 0o666 permissions on Snata and CMC final WAV outputs.

## v4.13 (2025-12-16)
- System Audit v4.13: Proactively upgraded FINA1 and FIMAI permissions to 0o666 to prevent 500 errors.

## v4.12 (2025-12-16)
- UI Upgrade v4.12: Implemented Sidebar Accordion (Collapsed descriptions, Tooltips, Active-Expansion) to optimize layout.

## v4.11 (2025-12-16)
- Permission Audit v4.11: Applied stable shell CP + 666 permissions to Snata, CMC, and XMIOX to eradicate 500 errors.

## v4.10 (2025-12-16)
- Stability Fix v4.10: Updated Fugue file writing to match P10NO (Shell CP + 666 Permissions) to resolve 500 errors.

## v4.09 (2025-12-16)
- Styling Fix v4.09: Restored ASCII Logo Gradient (Cyan-Purple-Pink-Yellow).

## v4.08 (2025-12-16)
- Fix v4.08: Fixed 500 Error on Downloads (Header Syntax Fix) + stabilized SNATA.

## v4.07 (2025-12-16)
- Hotfix v4.07: Fixed SNATA HTTP 400 error (file requirement) + Fixed ASCII Logo clipping.

## v4.06 (2025-12-16)
- UI Regression Fix: Fixed corrupted CSS (White BG) and SNATA Button state.

## v4.05 (2025-12-16)
- Emergency UI Repair (Restored CSS/JS), Fixed Fugue Silence (Normalized MIDI), Overhauled XMIOX (Sync Fix + Piano Transcriber for Drums).

## v4.01 (2025-12-16)
- Hotfix: Solved 500 Error in CMCMF/SNATA downloads by ensuring non-silent failure. Fully enabled SNATA dispatcher in main.py.

## v4.00 (2025-12-16)
- Major Release: Added SNATA.XMlX (Generative Sonata Module). Updated UI with Puce/Maroon theme and enforced consistent color borders for all PRO tools.

## v3.90 (2025-12-16)
- Added retry logic (3 attempts) to XMIOX for Music.AI job stability. Added env var override for MUSICAI_API_KEY.

## v3.89 (2025-12-16)
- Fixed 'malware' warning on Fugue MIDI downloads by repairing stitching logic. Fixed KeyError crashing CMCMF generation (renamed program->program_num).

## v3.88 (2025-12-16)
- Flattened CMCMF output files to root directory and applied strict permissions to fix Download 404/500 errors. Includes Song Generator logic hotfix (v3.87).

## v3.87 (2025-12-16)
- Hotfix for Song Generator ignoring settings. Added config.update(settings) to properly load genre/instruments from cmcmf.py output.

## v3.86 (2025-12-16)
- Refined CMCMF for strict Solo Mode (Classical genre, strict single instrument, 128 bars total). Added Fugue 500 Debug Logging.

## v3.86 (2025-12-16)
- Added verbose debug logging to main.py download route to diagnose file permission and access 500 errors. Deployed v3.85 CMCMF fixes.

## v3.85 (2025-12-16)
- Fixed CMCMF to strictly adhere to Custom Song Settings (Solo Mode) by forcing Song Generator to check CWD for configuration. Fixed output length issue by prioritizing the stitched Final MIDI over individual part files.

## v3.84 (2025-12-16)
- Major Fugue.py upgrade: length increased to ~4 mins, removed drum channel risk by renaming roles, added MIDI stitching, and enabled XMLX output generation.

## v3.83 (2025-12-16)
- Refactored CMCMF to strictly produce solo instrument output. Removed all accompaniment tracks and updated generation prompts to enforce solo context.

## v3.82 (2025-12-16)
- Fixed fugue.py usage error: now correctly handles positional arguments (input path, soundfont path) passed by main.py.

## v3.81 (2025-12-16)
- Hotfix: Added Fugue (and CMCMF) to Generative Tools list in main.py to resolve HTTP 400 'No file provided' error.

## v3.80 (2025-12-15)
- Reordered Sidebar (Free Top/Pro Bottom). Added error capturing to Fugue Generator to diagnose 400 errors.

## v3.79 (2025-12-15)
- Refined UI styles: Fugue Generator is now Dark Orange, Piano Tool (p2mix) is Black/White. Updated descriptions and tooltips.

## v3.78 (2025-12-15)
- Integrated Fugue Generator (3-Part Baroque Fugue) as a new PRO Generative Tool. Added fugue.py script and web UI interface.

## v3.77 (2025-12-15)
- Restored 4-Part CMCMF structure (8 bars each) and fixed p20convolver to prevent quadruple-length output (reduced 128->64 bars) to solve MAX_TOKENS crash.

## v3.76 (2025-12-15)
- Standardized all modules (CMCMF, 15010, FINA1, etc.) to use 0644 file permissions instead of 0777 to fix HTTP 500 errors on Cloud Run. Unified logging formats.

## v3.75 (2025-12-15)
- Stable Release: Fixed FINA1 UI & Download, Fixed CMCMF Token Explosion (3-Part Plan), Fixed Invisible Files on Local (wavF).

## v3.72 (2025-12-15)
- Update RoEx API Key

## v3.71 (2025-12-15)
- Fix left nav UI, CMCMF file permissions

## v3.69 (2025-12-15)
- Fix UI & Tokens

## v3.67 (2025-12-15)
- Simplify pipeline (no mastering)

## v3.65 (2025-12-15)
- Fixed P20CO/P10NP download perms

## v3.63 (2025-12-15)
- Fixed CMCMF EOFError in headless mode

## v3.62 (2025-12-15)
- Fixed CMCMF log buffering hang

## v3.60 (2025-12-15)
- Fixed WAV download 500 error

## v3.58 (2025-12-15)
- Reverted API input to WAV

## v3.56 (2025-12-15)
- Fixed XYMIX upload requirement

## v3.54 (2025-12-15)
- Fixed CMCMF args and enabled auto-run

## v3.53 (2025-12-15)
- Added midiutil, PyYAML, ruamel.yaml

## v3.52 (2025-12-15)
- Added missing colorama dependency

## v3.51 (2025-12-15)
- Fixed CMCMF transcoding error

## v3.50 (2025-12-14)
- Fix missing brace

## v3.49 (2025-12-14)
- Fixed syntax error in checkUploadState

## v3.48 (2025-12-14)
- Fixed sidebar navigation bug in unified_index.html

## v3.47 (2025-12-14)
- Fixed Navigation Bug: Repaired corrupted JavaScript syntax in unified_index.html that broke tool switching.

## v3.46 (2025-12-14)
- Fixed XYMIX UI: Now correctly shows upload box since it requires input. Confirmed Generative/Processing split.

## v3.44 (2025-12-14)
- Fixed 15010/XMIOX logic split. Fixed P10NO/P20CO 500 errors by ensuring input paths are valid. Added UUIDs to temp filenames. Added CMCMF to generative tool list.

## v3.43 (2025-12-14)
- Fixed Regression: Separated 15010 and XMIOX logic. 15010 correctly accepts 'fav', XMIOX correctly runs its own script.

## v3.42 (2025-12-14)
- Fixes for CMCMF: Added dependencies, fixed UI nav order, button size, and upload requirement logic.

## v3.42 (2025-12-14)
- Fixed 15010/XMIOX Argument Parsing: Now correctly respects user instrument preference (fav).

## v3.41 (2025-12-14)
- Added CMCMF.XMlX (Encore) Module: Classical Composition -> P20CO Pipeline + Soloist Selector. Fixed P10NO 500 Errors.

## v3.37 (2025-12-14)
- Fix 15010 logic with Max Notes default & Robust Perms

## v3.40 (2025-12-14)
- **XMIOX Alignment Upgrade**: 
    - Forced **ByteDance** transcription for all melodic stems (Piano, Bass, Keys, Other) to ensure consistent onset accuracy.
    - Added **Strict Time Padding**: Pads generated MIDI tracks to match exact source audio duration, preventing alignment drift during rendering.

## v3.39 (2025-12-14)
- **P20CO Logic Upgrade**: Implemented "Extend & Evolve" post-processing.
    - Generates a rich 3-layer composition: (1) Half-Speed Foundation, (2) Evolving Motif (2x), (3) High-Register Counterpoints.
    - **Strict Auto-Tune**: All evolved notes are snapped to the key before and after mutation to ensure perfect harmony.
    - Doubles output duration for a more complete musical idea.

## v3.38 (2025-12-14)
- Fixed 15010 `FileNotFoundError`: Removed redundant copy-delete loop that caused stems to delete themselves before transcription.
- Fixed 15010 Logic: Disabled generic transcription for Vocals/Drums/Other (Audio Only).
- Fixed P10NP/P20CO Final WAV 500 Error: Applied `chmod 777` to API downloads.

## v3.37 (2025-12-14)
- Fixed 15010 logic: Implemented "Max Notes" winner selection for default preference and robust permission hardening (chmod 777).

## v3.36 (2025-12-14)
- Fixed P10NO/P20CO 500 Errors by hardening copy logic (check=True) and permissions (chmod 777).

## v3.35 (2025-12-14)
- Restored Xymix logic and enforced shell-based WAV permissions to fix 500 errors.

## v3.34 (2025-12-14)
- Fixed HTTP 500 errors on P10NP/P20CO final WAVs.

## v3.33 (2025-12-14)
- Fixed P20CO HTTP 400 Error and Xymix Basic Pitch Model Path.

## v3.32 (2025-12-14)
- Fix P10NP/P20CO startup errors and JSNTH transcription in Xymix

## v3.31 (2025-12-13)
- Fixed P10NO/P20CO Argument Errors

## v3.30 (2025-12-13)
- Removed Authentication (Open Access), Fixed Xymix/15010 Bugs

## v3.28 (2025-12-13)
- Hotfix: Fix 15010 Regression (Double Demucs Call) & Xymix UI

## v3.27 (2025-12-13)
- Hotfix: Fix Xymix UI Crash (Missing HTML causing hang)

## v3.26 (2025-12-13)
- Hotfix: Fix Infinite Auth Loop (Added Stable SECRET_KEY)

## v3.25 (2025-12-13)
- Hotfix: Fix Duplicate Route Crash (AssertionError)

## v3.24 (2025-12-13)
- Hotfix: Fix Template Logic & Disable Cloud Storage

## v3.23 (2025-12-13)
- Hotfix: v3.23 Final Deployment Fix (Restored Routes)

## v3.22 (2025-12-13)
- Hotfix: Deployment Backend Fixes (Gunicorn, SoundFont Paths)

## v3.21 (2025-12-13)
- Implemented XYMIX (MUSIC.XMlX) UI with Two-Tier Dropdown and JSNTH support.

## v3.20 (2025-12-13)
- v3.20: Fix Download 500 (Robust Path Logic) & XYMIX XML Perms

## v3.19 (2025-12-13)
- v3.19: Hotfix for XMIOX Syntax Error & 15010 500 Fix

## v3.18 (2025-12-13)
- v3.18: App-Level Authentication (Frontend Overlay + Backend Verification)

## v3.17 (2025-12-13)
- v3.17 IAM Update: Switched to Google Groups (xmlx-pro-discuss@lign.dev)

## v3.16 (2025-12-13)
- v3.16: IAM Lockdown, Visual Polish (Gray/White), Interaction Fixes

## v3.14 (2025-12-13)
- Version Bump to 3.14 (Pi Edition)

## v3.13 (2025-12-13)
- Hotfix: Fixed JS Syntax Error in checkProAccess (v3.12 Regression)

## v3.12 (2025-12-13)
- Updated Domain Logic for free.xmlx.app & pro.xmlx.app

## v3.11 (2025-12-13)
- Implemented Frontend/Backend Upsell Locks (Pro tools visible but locked in Free tier)

## v3.10 (2025-12-13)
- Hardened 15010, FIMAI, FINA1, XMIOX against 500 Permission Errors (Force Delete Logic)

## v3.06 (2025-12-13)
- Added PRO.tools link with Access Check/Alert logic + API Ping endpoint

## v3.05 (2025-12-13)
- IAM Lockdown: Removed --allow-unauthenticated from PRO service deployment

## v3.04 (2025-12-13)
- Fixed P20CO 'file required' validation logic + added Zonal Redundancy flag fix

## v3.03 (2025-12-13)
- Fixed P20CO 500 error (hardened copy permissions) + Refined UI (match P10NO layout)

## v3.02 (2025-12-13)
- Refined P20CO UI Layout (Removed upload box, ensured Crimson)

## v3.01 (2025-12-13)
- Fixed P2mix regression by hardening permission handling and existing file cleanup

## v3.00 (2025-12-13)
- Intuitively solved a frustrating, hard-to-diagnose bug (xYmix case sensitivity)! (Credit: The Intuitive Developer). Also added Pro/Free tier deployment logic.

## v2.99 (2025-12-13)
- Unified Index UI Fix for P20CO (Hide Upload)

## v2.99 (2025-12-13)
- Added P20CO.XMlX module (Convolver)

## v2.98 (2025-12-13)
- Renamed xYmix.py to xymix.py to fix 500 errors (case sensitivity)

## v2.97 (2025-12-13)
- Fixed xYmix 500 errors (replaced copy2 with copyfile+chmod)

## v2.96 (2025-12-13)
- Fixed P10NO 500 errors (replaced copy2 with copyfile+chmod)

## v2.95 (2025-12-13)
- Fixed P10NO workflow slug and deprecation warnings

## v2.94 (2025-12-12)
- v2.93 hotfixes + P10NO API Key fix

## v2.93 (2025-12-12)
- **v2.94**: **Critical Stability & Permission Release**
    - **P10NO Fixes**:
        - Fixed `401 Unauthorized` error by syncing `MUSICAI_API_KEY` in `p10np.py`.
        - Added missing dependencies `music21` and `textblob` to `requirements.txt`.
        - Fixed `argparse` output filename handling.
    - **500 Error Fixes (XMIOX & 15010)**:
        - Replaced all instances of `shutil.copy2` and `shutil.copymode` with `shutil.copyfile` + `os.chmod(path, 0o644)`.
        - This prevents `demucs` output permissions (often restrictive) from being inherited by generated WAVs, ensuring they are readable by the Flask server.
    - **Debugging**:
        - Added `/debug/ls` endpoint to `main.py` to list ephemeral file permissions (`ls -l` style) for troubleshooting Cloud Run instances.
    - **UI**:
        - Confirmed restoration of **FIMAI** "Royal Purple" theme.

## v2.91 (2025-12-12)
- FINA1 Chmod/Norm Fix + Ice Blue Theme

## v2.90 (2025-12-12)
- Fix Input Link 500 Errors (Always Chmod)

## v2.89 (2025-12-12)
- Fix p2mix/fimai 500 Errors (Permissions)

## v2.88 (2025-12-12)
- Fix P10NO 400 Error Logic

## v2.87 (2025-12-12)
- Fix P10NO 400 and Upload Hang

## v2.86 (2025-12-12)
- Fix UI Bugs: P10NO Start & Module Switch Warning

## v2.85 (2025-12-12)
- Feature: Persistent Storage (GCS Fuse) & /download/listall Route

## v2.82 (2025-12-12)
- Fix xYmix (15010) 500 Errors (WAV permissions) and UI Options (Remove Drums, Default: 'I Love Them All')

## v2.81 (2025-12-12)
- Hotfix: Fix WAV permission 500 Errors by replicating xYmix copymode behavior

## v2.80 (2025-12-12)
- Integrated Music.AI Drumscribe (9-stem) with Hybrid Rendering (PySynth + FluidSynth) and MPS Acceleration

## v2.77 (2025-12-12)
- Switching to copyfile for 500 error fix

## v2.76 (2025-12-12)
- Parity fix for fimai download errors

## v2.75 (2025-12-12)
- Robust download fix for 500 errors

## v2.73 (2025-12-12)
- Fixed fimai.py arguments

## v2.72 (2025-12-11)
- Added missing musicai-sdk to requirements.txt

## v2.71 (2025-12-11)
- UI Polish: FIMAI Royal Theme & Nav Reorder, XMIOX Rainbow Border

## v2.70 (2025-12-11)
- Added FIMAI.XMlX (Neutral Stemming & Mastering) with LUFS control

## v2.54 (2025-12-11)
- Fixed RoEx TrackData Enums (InstrumentGroup, etc) preventing str error. Fixed UI JS not sending style parameter.

## v2.53 (2025-12-11)
- Fixed RoEx Enum Import: now using confirmed path roex_python.models.mixing.MusicalStyle.

## v2.52 (2025-12-11)
- Fixed RoEx API error: Converted 'musical_style' string argument to required Enum.

## v2.51 (2025-12-11)
- Fixed syntax error in unified_index.html (truncated javascript) that broke navigation.

## v2.50 (2025-12-11)
- Implemented Musical Style selection (UI, Backend, Script) to satisfy RoEx API requirement.

## v2.49 (2025-12-11)
- Fixed MultitrackMixRequest: Removed unsupported 'allow_clipping' argument.

## v2.48 (2025-12-11)
- Fixed MultitrackMixRequest args (tracks->track_data, moved return_stems). Updated Default Route to xYmix (MUSIC.XMlX).

## v2.47 (2025-12-11)
- Removed unsupported 'name' argument from MultitrackMixRequest instantiation.

## v2.46 (2025-12-11)
- Implemented RoEx API integration in `fina1.py`.
- Fixed `TrackData` instantiation with correct arguments (`track_url`, `instrument_group`).
- Added intelligent stereo panning (Guitar=Left, Piano=Right) and presence settings to widen soundstage.
