"""
fina1.py - Core Audio Processing Pipeline (v2.55)

This module implements the end-to-end audio processing workflow for the application.
Pipeline Stages:
1.  Source Separation (Demucs): Splits input audio into 6 stems (piano, guitar, drums, bass, vocals, other).
2.  RoEx Mixing (Cloud): Contextual mixing of stems using the RoEx API.
3.  RoEx Mastering (Cloud): Automated mastering of the mix to target LUFS.
4.  Normalization (Local): Final LUFS adjustment for user preference.
5.  XML Generation (XMLX): Metadata and file manifest generation.

AGENT NOTES:
- This file contains critical logic for interfacing with the RoEx API, including
  workarounds for blocking calls calling specific 'preview' methods.
- See individual functions for specific implementation details. 
"""
import argparse
import os
import sys
import shutil
import subprocess
import time
import requests # Fallback if library fails, but using library primarily
import xmlx
from pydub import AudioSegment

# RoEx Library
try:
    import roex_python
    # Try to find the client
    if hasattr(roex_python, 'RoExClient'):
        RoExClient = roex_python.RoExClient
    else:
        # Maybe it's in a submodule?
        print(f"[DEBUG] roex_python contents: {dir(roex_python)}", flush=True)
        # Try submodule import if needed, but for now just fail loudly with info
        raise ImportError("RoExClient not found in roex_python")
        
    # Utils
    try:
        from roex_python.utils import upload_file
    except ImportError:
         print("[DEBUG] roex_python.utils not found. Using local fallback?", flush=True)
         # Define local fallback or fail? User wants it working.
         # If utils missing, we can't upload easily.
         raise
         
except ImportError as e:
    print(f"[!] RoEx Import Error: {e}", flush=True)
    print(f"[DEBUG] sys.path: {sys.path}", flush=True)
    try:
        import subprocess
        print("[DEBUG] pip list:", flush=True)
        subprocess.run([sys.executable, "-m", "pip", "list"], check=False)
    except: pass
    sys.exit(1)

# API KEYS (Hardcoded as per user request, typically env vars)
ROEX_API_KEY_DEV = "AIzaSyCRCHM0uc0tWJgEUPEu0RZULguJw_TWrw8"
ROEX_API_KEY_PROD = "AIzaSyB07ucMuUlXIbFvJ2q5a9Cv2b975Bkc18M"

# Use PROD by default
API_KEY = ROEX_API_KEY_PROD

def normalize_lufs(input_path, output_path, lufs=-14.0):
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-af', f'loudnorm=I={lufs}:TP=-1.0:LRA=11',
        '-ar', '44100',
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try: os.chmod(output_path, 0o644)
    except: pass

def normalize_db(input_path, output_path, db=-8.0):
    # Peak normalization using ffmpeg-normalize or simple gain?
    # Using simple ffmpeg filter for peak
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-af', f'volume={db}dB', # Wait, this adds gain. That's not Normalize TO -8dB.
        # To normalize TO peak -8dB, we need loudnorm or 2-pass.
        # Let's use loudnorm with high target or simple normalization if possible.
        # Actually, let's use pydub for exact peak normalization
        'temp_dummy.wav' # subprocess requires list
    ]
    # Pydub Approach
    try:
        audio = AudioSegment.from_wav(input_path)
        change_in_dBFS = db - audio.max_dBFS
        normalized_sound = audio.apply_gain(change_in_dBFS)
        normalized_sound.export(output_path, format="wav")
    except Exception as e:
        print(f"   [!] Norm failed: {e}", flush=True)

import torch # Added for device check

def separate_6_stems(input_wav, output_dir):
    # Check for CUDA availability
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"\n[2/8] Separating 6 Stems (Demucs) on {device.upper()}...", flush=True)
    
    cmd = [
        sys.executable, "-m", "demucs.separate",
        "-n", "htdemucs_6s",
        "-d", device, # Explicitly pass device
        "--out", output_dir,
        input_wav
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(f"[!] Demucs Failed. Exit Code: {e.returncode}", flush=True)
        print(f"[!] STDOUT/STDERR:\n{e.stdout.decode()}", flush=True)
        raise
    
    track_name = os.path.splitext(os.path.basename(input_wav))[0]
    result_dir = os.path.join(output_dir, "htdemucs_6s", track_name)
    
    stems = {
        'vocals': os.path.join(result_dir, "vocals.wav"),
        'drums': os.path.join(result_dir, "drums.wav"),
        'bass': os.path.join(result_dir, "bass.wav"),
        'guitar': os.path.join(result_dir, "guitar.wav"),
        'piano': os.path.join(result_dir, "piano.wav"),
        'other': os.path.join(result_dir, "other.wav")
    }
    return stems

# ------------------------------------------------------------------
# Main Pipeline
# ------------------------------------------------------------------
def pipeline_fina1(input_wav, output_wav, user_lufs=-14.0, style="OTHER"):
    output_dir = os.path.dirname(output_wav)
    base_name = os.path.splitext(os.path.basename(input_wav))[0]
    xml_output = os.path.join(output_dir, f"{base_name}_fina1.xml")
    temp_demucs = os.path.join(output_dir, "temp_demucs_fina1")
    
    print(f"--- FINA1 Pipeline Initiated ---", flush=True)
    print(f"--- Target Final LUFS: {user_lufs} ---", flush=True)
    print(f"--- Musical Style: {style} ---", flush=True)
    
    # 1. Source Prep
    print(f"\n[1/8] Source Preparation...", flush=True)
    
    # Check if input exists and size
    if not os.path.exists(input_wav):
        print(f"[!] Input file not found: {input_wav}", flush=True)
        return
    
    input_size = os.path.getsize(input_wav)
    print(f"   > Input: {input_wav} (Size: {input_size} bytes)", flush=True)
        
    if input_size < 100:
        print("[!] Input file suspiciously small. Analyzing content...", flush=True)
        try:
            with open(input_wav, 'r', errors='ignore') as f:
                head = f.read(100)
                print(f"   > Header: {head}", flush=True)
        except: pass
        
    # Sanitize input (ffmpeg -> pcm_s16le wav)
    # This fixes issues with weird codecs, corrupt headers, or just "bad" wavs
    sanitized_wav = os.path.join(output_dir, f"clean_{os.path.basename(input_wav)}")
    print(f"   > Sanitizing/Converting to safe WAV...", flush=True)
    
    clean_cmd = [
        'ffmpeg', '-y', 
        '-i', input_wav,
        '-c:a', 'pcm_s16le',
        '-ar', '44100',
        sanitized_wav
    ]
    try:
        subprocess.run(clean_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try: os.chmod(sanitized_wav, 0o644)
        except: pass
        print(f"   > Sanitized input created: {sanitized_wav}", flush=True)
        input_wav = sanitized_wav
    except subprocess.CalledProcessError as e:
        print(f"[!] FFmpeg Sanitization Failed. Code: {e.returncode}", flush=True)
        print(f"[!] Error: {e.stderr.decode()}", flush=True)
        # If sanitization fails, the input is likely garbage. We should start throwing errors.
        raise Exception("Input file is corrupt or unreadable.")
    except Exception as e:
        print(f"[!] Sanitization Error: {e}", flush=True)
        # Fallback to copy?
        input_copy = os.path.join(output_dir, os.path.basename(input_wav))
        if os.path.abspath(input_wav) != os.path.abspath(input_copy):
            if os.path.exists(input_copy):
                try: os.remove(input_copy)
                except: pass
            shutil.copyfile(input_wav, input_copy)
        input_wav = input_copy
    
    # ALWAYS ensure input is readable
    try: os.chmod(input_wav, 0o644)
    except: pass

    # 2. Separation
    stems = separate_6_stems(input_wav, temp_demucs)
    
    # 3. [SKIPPED] Normalize Stems to -8dB (User Request: Raw Stems)
    # Instead, we just ensure the RAW stems are readable (chmod 644)
    # and pass them directly to RoEx.
    print(f"\n[3/8] Preparing Stems (Raw/Chmod)...", flush=True)
    norm_stems = {}
    for s_name, s_path in stems.items():
        if os.path.exists(s_path):
            try: os.chmod(s_path, 0o644)
            except: pass
            norm_stems[s_name] = s_path
            print(f"[OUTPUT] Stem {s_name.capitalize()}|{s_path}", flush=True)
            
    # 4. RoEx Mastering (Individual Stem "Mastering"/Enhancement)
    # User Requirements: "master each stem individually... taking into account... combined"
    # This implies a Multitrack Mix where we get processed stems back.
    print(f"\n[4/8] RoEx Processing (Contextual Mastering)...", flush=True)
    
    client = RoExClient(api_key=API_KEY)
    
    # Upload Stems
    uploaded_tracks = []
    track_type_map = {
        'vocals': 'vocals', 'drums': 'drums', 'bass': 'bass', 
        'guitar': 'other', 'piano': 'other', 'other': 'other' 
    }
    
    # We need to upload them. RoEx python has upload utils.
    # We should use the normalized stems.
    roex_stem_urls = {}
    
    # Set Env Var for RoEx internals if needed
    os.environ["ROEX_API_KEY"] = API_KEY
    try:
        for s_name, path in norm_stems.items():
            print(f"   > Uploading {s_name}...", flush=True)
            # Error: upload_file() missing 1 required positional argument: 'file_path'
            # Implies signature is upload_file(client, file_path) or similar.
            # Passing client as first arg.
            url = upload_file(client, path)
            # Note: Checking signature of upload_file. If it returns url, great.
            # If RoExClient handles it, even better. Assuming client.upload_file or util.
            roex_stem_urls[s_name] = url
            
            uploaded_tracks.append({
                "url": url,
                "name": s_name,
                "type": track_type_map.get(s_name, 'other')
            })
            
        print(f"   > [DEBUG] RoExClient attributes: {dir(client)}", flush=True)

        # Mix Task
        # Attempting client.mix based on research
        # Mix Task
        # Debug output shows 'create_mix_preview' but no 'create' or 'mix'.
        # Hypothesis: Workflow is Create Preview -> Retrieve Final Mix.
        try:
            print("   > Creating Mixing Task (client.mix.create_mix_preview)...", flush=True)
            
            # Use proper models if available
            try:
                # Attempt explicit model import
                from roex_python.models import MultitrackMixRequest, TrackData
                from roex_python.models.mixing import MusicalStyle, InstrumentGroup, PresenceSetting, PanPreference, ReverbPreference
            except ImportError as e:
                print(f"   > [CRITICAL] Import Error: {e}", flush=True)
                raise e
            
            # DEBUG: Introspect TrackData to find correct fields
            # print(f"   > [DEBUG] TrackData fields: {getattr(TrackData, '__annotations__', 'Unknown')}", flush=True)
            
            req_tracks = []
            for t in uploaded_tracks:
                # Intelligent Distribution Logic
                # Types: 'vocals', 'drums', 'bass', 'other' (which includes guitar/piano mapped to 'other' typically, 
                # but we preserved names in 'name' or 'type'?)
                # Wait, track_type_map in lines 197-200 mapped guitar/piano to 'other' for the 'type' field?
                # Line 199: 'guitar': 'other', 'piano': 'other'
                # So t['type'] will be 'other' for guitar/piano.
                # We need to use t['name'] to distinguish!
                
                t_name = t['name'].lower()
                
                # Defaults
                i_group = InstrumentGroup.OTHER_GROUP1
                pan_pref = PanPreference.CENTRE
                pres_set = PresenceSetting.NORMAL
                
                if 'vocals' in t_name:
                    i_group = InstrumentGroup.VOCAL_GROUP
                    pan_pref = PanPreference.CENTRE
                    pres_set = PresenceSetting.LEAD
                elif 'drums' in t_name:
                    i_group = InstrumentGroup.DRUMS_GROUP
                    pan_pref = PanPreference.CENTRE
                    pres_set = PresenceSetting.LEAD
                elif 'bass' in t_name:
                    i_group = InstrumentGroup.BASS_GROUP
                    pan_pref = PanPreference.CENTRE
                    pres_set = PresenceSetting.NORMAL
                elif 'guitar' in t_name:
                    i_group = InstrumentGroup.E_GUITAR_GROUP
                    pan_pref = PanPreference.LEFT
                    pres_set = PresenceSetting.NORMAL
                elif 'piano' in t_name:
                    i_group = InstrumentGroup.KEYS_GROUP
                    pan_pref = PanPreference.RIGHT
                    pres_set = PresenceSetting.NORMAL
                elif 'other' in t_name:
                    i_group = InstrumentGroup.BACKING_TRACK_GROUP
                    pan_pref = PanPreference.CENTRE
                    pres_set = PresenceSetting.BACKGROUND

                # Corrected TrackData instantiation with Enums
                req_tracks.append(TrackData(
                    track_url=t['url'],
                    instrument_group=i_group,
                    presence_setting=pres_set,
                    pan_preference=pan_pref,
                    reverb_preference=ReverbPreference.NONE
                ))
            # DEBUG: Introspect MultitrackMixRequest
            # print(f"   > [DEBUG] MultitrackMixRequest fields: {getattr(MultitrackMixRequest, '__annotations__', 'Unknown')}", flush=True)

            try:
                style_enum = MusicalStyle[style] 
                print(f"   > [DEBUG] Converted '{style}' to {style_enum}", flush=True)
            except KeyError:
                print(f"   > [WARN] Style '{style}' not found in Enum. Defaulting to OTHER.", flush=True)
                style_enum = MusicalStyle.OTHER

            mix_request = MultitrackMixRequest(
                track_data=req_tracks,
                return_stems=True,
                musical_style=style_enum,
                webhook_url="https://postman-echo.com/post" # Robust dummy URL that accepts POST and returns 200
            )
            
            # --- DEBUG PAYLOAD ---
            print("\n--- DEBUG: RoEx Payload Inspection ---", flush=True)
            print(f"Musical Style Enum: {mix_request.musical_style} (Value: {mix_request.musical_style.value})", flush=True)
            for idx, tr in enumerate(mix_request.track_data):
                print(f"Track {idx}: URL={tr.track_url} (Type: {type(tr.track_url)})", flush=True)
                print(f"         Group={tr.instrument_group} (Value: {tr.instrument_group.value})", flush=True)
                print(f"         Pan={tr.pan_preference} (Value: {tr.pan_preference.value})", flush=True)
                print(f"         Pres={tr.presence_setting} (Value: {tr.presence_setting.value})", flush=True)
                print(f"         Rev={tr.reverb_preference} ({tr.reverb_preference.value})", flush=True)
                
            # Try to serialize manually to see if it works
            import json
            try:
                # Assuming generic object structure if not pydantic
                def default_serializer(obj):
                    if hasattr(obj, 'value'): return obj.value
                    if hasattr(obj, '__dict__'): return obj.__dict__
                    return str(obj)
                
                print(f"JSON Dump Attempt: {json.dumps(mix_request, default=default_serializer, indent=2)}", flush=True)
            except Exception as e:
                print(f"Could not dump JSON: {e}", flush=True)
            print("--------------------------------------\n", flush=True)
            # ---------------------

            # Trying positional first arg with Model
            mix_task = client.mix.create_mix_preview(mix_request)
            
            # Assuming mix_task has multitrack_task_id
            task_id = getattr(mix_task, 'multitrack_task_id', None)
            if not task_id:
                 # Fallback introspection if attribute name differs
                 print(f"   > [WARN] 'multitrack_task_id' not found. Attributes: {dir(mix_task)}", flush=True) 
                 # Try to find anything with 'id' in name
                 for attr in dir(mix_task):
                     if 'id' in attr.lower() and not attr.startswith('_'):
                         task_id = getattr(mix_task, attr)
                         print(f"   > [INFO] Found likely ID attribute: {attr} = {task_id}", flush=True)
                         break
            
            print(f"   > Mix Task Created. ID: {task_id}", flush=True)
            
        except Exception as e:
            print(f"   [!] Error creating mix preview: {e}", flush=True)
            raise e
        
        # --- POLLING LOOP ---
        print(f"   > Polling status for Task ID: {task_id}...", flush=True)
        
        # Status Method verified via debug: 'retrieve_preview_mix'
        status_method_name = 'retrieve_preview_mix'
        print(f"   > Using Status Method: {status_method_name}", flush=True)
        status_method = getattr(client.mix, status_method_name)
        
        # --- BLOCKING RETRIEVAL ---
        # Evidence suggests 'retrieve_preview_mix' blocks until completion or timeout.
        # It returns the RESULT object (with mix_url), not a status object.
        # --- BLOCKING RETRIEVAL ---
        # AGENT NOTE (v2.55):
        # We discovered that `retrieve_preview_mix` (and similar preview methods) are BLOCKING.
        # They internally poll the server and only return when the task is complete (or timeout).
        # DO NOT wrap these in a polling loop, or you will wait 30x longer than necessary.
        # They return a RESULT object (often a Dict in recent versions) directly.
        print(f"   > Waiting for Mix Result (Blocking Call)...", flush=True)
        
        try:
            # This call blocks and polls internally
            result = status_method(task_id)
            print("   > Mix Preview Returned!", flush=True)
            
            # Debug Result
            print(f"   > [DEBUG] Result Object: {result}", flush=True)
            print(f"   > [DEBUG] Result Dir: {dir(result)}", flush=True)
            if hasattr(result, '__dict__'):
                print(f"   > [DEBUG] Result Dict: {result.__dict__}", flush=True)
            
            final_download_url = None
            if isinstance(result, dict):
                final_download_url = result.get('download_url_preview_mixed')
                if not final_download_url: final_download_url = result.get('mix_url')
            else:
                final_download_url = getattr(result, 'mix_url', getattr(result, 'url', None))
            
            if final_download_url:
                 print(f"   > Final Mix URL: {final_download_url}", flush=True)
                 # Download Preview for verification
                 try:
                    import requests
                    r = requests.get(final_download_url)
                    if r.status_code == 200:
                        out_path = os.path.join(output_dir, f"{os.path.basename(input_wav).split('.')[0]}_preview.wav")
                        with open(out_path, 'wb') as f:
                            f.write(r.content)
                        print(f"   > [SUCCESS] Downloaded Preview to: {out_path}", flush=True)
                    else:
                        print(f"   > [ERR] Failed to download: {r.status_code}", flush=True)
                 except Exception as e:
                    print(f"   > [ERR] Download Exception: {e}", flush=True)
            else:
                 print("   > [WARN] Result object returned but no 'mix_url' found.", flush=True)

        except Exception as e:
            print(f"   [!] Error retrieving mix result: {e}", flush=True)
            raise e

        # Retrieve Full Result Logic
        try:
            # We need 'result' object for downstream logic (stems, mix_url)
            if hasattr(client.mix, 'retrieve_mix_preview'):
                result = client.mix.retrieve_mix_preview(task_id)
            else:
                 # Fallback
                 result = {'download_url_preview_mixed': final_download_url, 'stems': {}}

        except Exception as e:
            print(f"   > [WARN] Error retrieving final result object: {e}", flush=True)
            result = {'download_url_preview_mixed': final_download_url, 'stems': {}}

        processed_stems = {}
        
        # 5. Combine into 0F1M
        print(f"\n[5/8] Assembling 0F1M (Initial Merge)...", flush=True)
        
        # Extract Mix URL safely (Dict or Object)
        mix_url_dl = None
        if isinstance(result, dict):
             mix_url_dl = result.get('download_url_preview_mixed')
             if not mix_url_dl: mix_url_dl = result.get('mix_url')
        else:
             mix_url_dl = getattr(result, 'mix_url', getattr(result, 'url', None))
        
        # Handle "Preview" URL if mix didn't return one
        if not mix_url_dl and final_download_url:
            mix_url_dl = final_download_url

        if mix_url_dl:
            print(f"   > Mix URL Found: {mix_url_dl}", flush=True)
            
            # Determine extension
            ext = ".wav"
            if ".mp3" in mix_url_dl.lower(): ext = ".mp3"
            
            temp_dl_path = os.path.join(output_dir, f"{base_name}_0F1M_temp{ext}")
            f1m_0_path = os.path.join(output_dir, f"{base_name}_0F1M.wav")

            resp = requests.get(mix_url_dl)
            if resp.status_code == 200:
                with open(temp_dl_path, 'wb') as f:
                    f.write(resp.content)
                
                # Convert to WAV if needed
                if ext == ".mp3":
                     print(f"   > Converting MP3 to WAV...", flush=True)
                     try:
                         from pydub import AudioSegment
                         audio = AudioSegment.from_mp3(temp_dl_path)
                         audio.export(f1m_0_path, format="wav")
                         # Remove temp mp3
                         os.remove(temp_dl_path)
                     except Exception as e:
                         print(f"   [!] Error converting MP3 to WAV: {e}. Using raw file.", flush=True)
                         os.rename(temp_dl_path, f1m_0_path) # Fallback
                elif temp_dl_path != f1m_0_path:
                     os.rename(temp_dl_path, f1m_0_path)
                
                try: os.chmod(f1m_0_path, 0o666)
                except: pass
                print(f"[OUTPUT] 0F1M (RoEx Mix)|{f1m_0_path}", flush=True)
            else:
                raise Exception(f"Failed to download mix: {resp.status_code}")
        else:
            raise Exception("No Mix URL available for download.")

        # Download Stems (for XML links)
        # Handle Dict or Object structure
        stems_iterable = []
        if isinstance(result, dict):
            # Dict: {'uuid.mp3': 'url'}
            s_dict = result.get('stems', {})
            stems_iterable = [{'name': k, 'url': v} for k, v in s_dict.items()]
        elif hasattr(result, 'stems'):
            # Object: List of objects with .name, .url
             stems_iterable = result.stems
        
        if stems_iterable:
             for s_entry in stems_iterable:
                 # Normalize entry
                 if isinstance(s_entry, dict):
                     s_name = s_entry.get('name', 'unknown')
                     s_url = s_entry.get('url')
                 else:
                     s_name = getattr(s_entry, 'name', 'unknown')
                     s_url = getattr(s_entry, 'url', None)
                 
                 if s_url:
                     # Clean name?
                     safe_s_name = s_name.replace('.mp3', '').replace('.wav', '')
                     p_path = os.path.join(output_dir, f"{base_name}_{safe_s_name}_roex.wav") # Assuming we want to track them
                     # For now, simplistic download (might be MP3)
                     # Not critically converting stems since XML just links them.
                     # But valid wav structure is better.
                     try:
                         r_s = requests.get(s_url)
                         with open(p_path, 'wb') as f:
                             f.write(r_s.content)
                         processed_stems[safe_s_name] = p_path
                         print(f"[OUTPUT] Mastered Stem ({safe_s_name})|{p_path}", flush=True)
                     except: pass
        
    except Exception as e:
        print(f"[!] RoEx Error: {e}", flush=True)
        # Fallback if RoEx fails? 
        # User requested "new module... making use of brand new API". 
        # If API fails, we probably should fail or just do local mix. 
        # Let's fail loudly so user sees API issue.
        return

    # 6. Master 0F1M -> 1F1M (-14 LUFS)
    # Using RoEx Mastering
    print(f"\n[6/8] RoEx Mastering 0F1M to -14 LUFS...", flush=True)
    
    f1m_1_path = os.path.join(output_dir, f"{base_name}_1F1M.wav")

    try:
        # Upload 0F1M
        mix_url = upload_file(client, f1m_0_path)
        
        # Method verified via debug: 'create_mastering_preview'
        master_method_name = 'create_mastering_preview'
        print(f"   > Using Mastering Method: {master_method_name}", flush=True)
        master_method = getattr(client.mastering, master_method_name)

        master_task = master_method(
            track_url=mix_url,
            settings={
                "target_lufs": -14,
                "style": "balanced"
            }
        )
        
        # Robust ID Retrieval
        m_task_id = getattr(master_task, 'mastering_task_id', getattr(master_task, 'id', None))
        if not m_task_id:
             # Fallback
             for attr in dir(master_task):
                 if 'id' in attr.lower() and not attr.startswith('_'):
                     m_task_id = getattr(master_task, attr)
                     break
        
        print(f"   > Task ID: {m_task_id}. Processing...", flush=True)
        
        # Blocking Retrieval Logic (mirroring mix logic)
        # AGENT NOTE: Same pattern as Mixing. 'retrieve_preview_master' blocks until done.
        m_result = None
        try:
            retrieve_method_name = 'retrieve_preview_master'
            if hasattr(client.mastering, retrieve_method_name):
                print(f"   > Waiting for Master Result (Blocking Call)...", flush=True)
                retrieve_method = getattr(client.mastering, retrieve_method_name)
                m_result = retrieve_method(m_task_id)
                print("   > Master Preview Returned!", flush=True)
            else:
                raise Exception("No retrieve_preview_master method found")
                
        except Exception as e:
            print(f"   > [WARN] Error retrieving master result: {e}", flush=True)
            raise e
            
        # Extract URL
        m_url = None
        if isinstance(m_result, dict):
            # Inspect keys if needed, betting on 'download_url...' pattern
            # print(f"   > [DEBUG] Master Result Keys: {m_result.keys()}", flush=True)
            m_url = m_result.get('download_url_preview_mastered')
            if not m_url: m_url = m_result.get('master_url')
        else:
            m_url = getattr(m_result, 'master_url', getattr(m_result, 'url', None))

        if m_url:
            # Check extension
            ext = ".wav"
            if ".mp3" in m_url.lower(): ext = ".mp3"
            
            temp_dl_path = os.path.join(output_dir, f"{base_name}_1F1M_temp{ext}")
            
            # Download
            resp = requests.get(m_url)
            if resp.status_code == 200:
                with open(temp_dl_path, 'wb') as f:
                    f.write(resp.content)
                
                # Convert if mp3
                if ext == ".mp3":
                     try:
                         from pydub import AudioSegment
                         audio = AudioSegment.from_mp3(temp_dl_path)
                         audio.export(f1m_1_path, format="wav")
                         os.remove(temp_dl_path)
                     except Exception as e:
                         print(f"   [!] Error converting Master MP3: {e}", flush=True)
                         os.rename(temp_dl_path, f1m_1_path)
                elif temp_dl_path != f1m_1_path:
                     os.rename(temp_dl_path, f1m_1_path)
            else:
                 raise Exception("Failed to download master")
        else:
             raise Exception("No Master URL in result")
             
        try: os.chmod(f1m_1_path, 0o644)
        except: pass
        print(f"[OUTPUT] 1F1M (Pre-Master)|{f1m_1_path}", flush=True)
        
    except Exception as e:
        print(f"[!] RoEx Mastering Error: {e}", flush=True)
        # Fallback: Copy 0F1M to 1F1M?
        shutil.copyfile(f1m_0_path, f1m_1_path)

    # 7. Final Norm (User LUFS) -> FF1M
    print(f"\n[7/8] Final Normalization to {user_lufs} LUFS...", flush=True)
    
    # We output to the 'output_wav' argument location as the Final
    normalize_lufs(f1m_1_path, output_wav, lufs=float(user_lufs))
    try: os.chmod(output_wav, 0o644)
    except: pass
    print(f"[OUTPUT] FF1M (Final)|{output_wav}", flush=True)
    
    # 8. XML Generation
    print(f"\n[8/8] Generating XML...", flush=True)
    stems_data = {}
    for s_name in ['vocals', 'drums', 'bass', 'guitar', 'piano', 'other']:
        entry = {}
        # Raw/Norm Stem
        if s_name in norm_stems: entry['audio'] = norm_stems[s_name]
        # Processed Stem (if available) as 'render' type (closest fit in XML schema)
        if s_name in processed_stems: entry['render'] = processed_stems[s_name]
        stems_data[s_name] = entry
        
    xmlx.generate_xml(input_wav, xml_output, final_mix_path=output_wav, stems=stems_data)
    print(f"[OUTPUT] XML|{xml_output}", flush=True)
    print("---------------------------------------------------", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_wav")
    parser.add_argument("soundfont", nargs='?') # Not used but passed by main
    parser.add_argument("--output", "-o", default="out.wav")
    parser.add_argument("--lufs", default=-14.0)
    parser.add_argument("--style", default="OTHER")
    args = parser.parse_args()
    
    pipeline_fina1(args.input_wav, args.output, args.lufs, args.style)
