"""
fimai.py - Music.AI Audio Processing Pipeline (v3.0)

Implements the 2-step Music.AI workflow:
1. Separation (1In-6Stems): Custom Workflow.
2. Mixing/Mastering (6In-1WAV): Custom Workflow (merging stems).

Dependencies:
- musicai_sdk
- xmlx
- fina1 (for normalization util)
"""
import os
import sys
import time
import shutil
import argparse
import requests
import musicai_sdk
import xmlx
from fina1 import normalize_lufs

# --- CONFIG ---
API_KEY = "0b8c5b07-182e-4e47-a97d-34d023203a91"
# Workflow Slugs (User Updated)
WF_SLUG_SEP = "1in-6stems"
WF_SLUG_MIX = "6in-1wav"

class MusicAiPipeline:
    def __init__(self):
        try:
            # Initialize Client
            # Standard class name speculation, usually MusicAiClient
            if hasattr(musicai_sdk, 'MusicAiClient'):
                self.client = musicai_sdk.MusicAiClient(api_key=API_KEY)
            else:
                 # Fallback if class name differs (based on debug script findings)
                 clients = [x for x in dir(musicai_sdk) if 'Client' in x]
                 if clients:
                     self.client = getattr(musicai_sdk, clients[0])(api_key=API_KEY)
                 else:
                     raise ImportError("Could not find Client class in musicai_sdk")
        except Exception as e:
            print(f"[!] Init Failed: {e}")
            sys.exit(1)

    def upload(self, file_path):
        print(f"   > Uploading {os.path.basename(file_path)}...", flush=True)
        # return self.client.upload_file(file_path) # Assuming standard method
        if hasattr(self.client, 'upload_file'):
            return self.client.upload_file(file_path)
        else:
            raise NotImplementedError("Client has no upload_file method")

    def run_job(self, name, workflow_id, params):
        print(f"   > Starting Job '{name}' (WF: {workflow_id})...", flush=True)
        
        # Create Job
        # Usually client.create_job or client.jobs.create
        # Debug script showed 'add_job' inputs: job_name, workflow_slug, params
        job = self.client.add_job(job_name=name, workflow_slug=workflow_id, params=params)
        job_id = getattr(job, 'id', job.get('id') if isinstance(job, dict) else str(job))
        
        print(f"     Job ID: {job_id}. Waiting...", flush=True)
        
        # Wait
        # Debug script showed 'wait_for_job_completion'
        if hasattr(self.client, 'wait_for_job_completion'):
            result = self.client.wait_for_job_completion(job_id)
            return result
        else:
            # Manual Poll
            while True:
                status = self.client.get_job(job_id)
                s_str = getattr(status, 'status', status.get('status') if isinstance(status, dict) else 'UNKNOWN')
                if s_str == 'SUCCEEDED':
                    return status
                elif s_str == 'FAILED':
                    raise Exception(f"Job Failed: {status}")
                time.sleep(5)

    def download(self, url, dest_path):
        print(f"   > Downloading {dest_path}...", flush=True)
        if os.path.exists(dest_path):
            try: os.remove(dest_path)
            except: pass
        with requests.get(url, stream=True) as r:
            r.raise_for_status()
            with open(dest_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)

    def process(self, input_wav, output_wav, target_lufs=-14.0):
        print(f"--- Music.AI Pipeline: {input_wav} ---", flush=True)
        
        # --- PREP: Copy Input to Output Dir for Download Link ---
        output_dir = os.path.dirname(output_wav)
        input_copy = os.path.join(output_dir, os.path.basename(input_wav))
        
        # Only copy if paths differ to avoid corruption
        if os.path.abspath(input_wav) != os.path.abspath(input_copy):
            try:
                if os.path.exists(input_copy):
                    try: os.remove(input_copy)
                    except: pass
                shutil.copy2(input_wav, input_copy)
                try: os.chmod(input_copy, 0o644)
                except: pass
                print(f"     [DEBUG] Copied input to {input_copy}", flush=True)
            except Exception as e:
                print(f"     [WARN] Check input copy failed: {e}", flush=True)
                input_copy = input_wav

        # ALWAYS ensure input is readable (Flask upload might be 600)
        try: os.chmod(input_copy, 0o644)
        except: pass

        # Emit Input Link
        print(f"[OUTPUT] Input Audio|{input_copy}", flush=True)
        
        # 1. Upload
        input_url = self.upload(input_wav)
        print(f"     URL: {input_url}", flush=True)
        
        # 2. Separation
        print(f"\n[1/3] Separation (1In-6Stems)...", flush=True)
        sep_result = self.run_job(
            name=f"Sep-{os.path.basename(input_wav)}",
            workflow_id=WF_SLUG_SEP,
            params={'inputUrl': input_url} # Assuming standard input param
        )
        
        # Extract Outputs
        # Result structure usually has 'outputs' key or attr
        # Extract Outputs
        # Result structure usually has 'outputs' key or attr
        print(f"     [DEBUG] Sep Result Type: {type(sep_result)}", flush=True)
        print(f"     [DEBUG] Sep Result Dir: {dir(sep_result)}", flush=True)
        if hasattr(sep_result, '__dict__'):
             print(f"     [DEBUG] Sep Result Dict: {sep_result.__dict__}", flush=True)

        if isinstance(sep_result, dict):
            # Result is directly in 'result' key based on debug inspection
            outputs = sep_result.get('result', {})
        else:
            outputs = getattr(sep_result, 'result', {})
            if outputs is None: outputs = {}

        print(f"     Stems Found: {list(outputs.keys())}", flush=True)
        
        # 3. Mixing
        print(f"\n[2/3] Mixing (6In-1WAV)...", flush=True)
        # Pass ALL separation outputs as inputs to mixing workflow
        # Assuming WS2 inputs match WS1 output keys
        mix_result = self.run_job(
            name=f"Mix-{os.path.basename(input_wav)}",
            workflow_id=WF_SLUG_MIX,
            params=outputs 
        )
        
        # Extract Final Mix URL
        if isinstance(mix_result, dict):
            mix_outputs = mix_result.get('result', {})
        else:
            mix_outputs = getattr(mix_result, 'result', {})
            
        print(f"     Mix Outputs: {list(mix_outputs.keys())}", flush=True)
        
        # Heuristic to find the wav url
        # Likely just one output
        mix_url = list(mix_outputs.values())[0] if mix_outputs else None
        
        if not mix_url:
            raise Exception("No mix URL found in result")
            
        # 4. Finalize
        print(f"\n[3/3] Finalizing...", flush=True)
        raw_out = output_wav.replace(".wav", "_raw.wav")
        self.download(mix_url, raw_out)
        try: os.chmod(raw_out, 0o666)
        except: pass
        
        # Normalize
        print(f"     Normalizing to {target_lufs} LUFS...", flush=True)
        normalize_lufs(raw_out, output_wav, lufs=target_lufs)
        print(f"     Saved: {output_wav}", flush=True)
        if os.path.exists(output_wav):
            try: os.chmod(output_wav, 0o666)
            except: pass
            print(f"[OUTPUT] Final Audio|{output_wav}", flush=True)
        else:
            print("[!] Error: Output file not created.", flush=True)
        
        # XML
        xmlx.generate_xml(input_wav, output_wav.replace(".wav", ".xml"), final_mix_path=output_wav)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_wav", help="Input WAV file")
    # Legacy argument from main.py (soundfont path), ignored here but must be consumed
    parser.add_argument("soundfont", nargs='?', help="Legacy Soundfont Path (Ignored)")
    parser.add_argument("--output", required=True, help="Output WAV file")
    parser.add_argument("--lufs", type=float, default=-14.0, help="Target LUFS")
    
    args = parser.parse_args()

    pipeline = MusicAiPipeline()
    pipeline.process(args.input_wav, args.output, target_lufs=args.lufs)
