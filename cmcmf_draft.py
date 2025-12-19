import argparse
import os
import subprocess
import shutil
import json
import yaml
import time
import random
try:
    from cmc_core import song_generator
except ImportError:
    song_generator = None # Handle gracefully or ensure path
import p20convolver

# --- Configuration ---
# Gemini API Key (Secure Load)
API_KEY = os.environ.get("GEMINI_API_KEY")
SOUNDFONT_NAME = "GeneralUser-GS.sf2"

def pipeline_cmcmf(prompt, instrument_id, output_xml_path, soundfont_path):
    output_dir = os.path.dirname(output_xml_path)
    base_name = os.path.splitext(os.path.basename(output_xml_path))[0]
    
    print(f"--- Processing CMCMF.XMlX: {prompt} ---", flush=True)

    # 1. Config Generation
    # We need to programmatically create the config for CMC
    # CMC expects: config.yaml, song_settings.json.
    # We will write them to a temp folder specific to this run to avoid collisions.
    run_id = f"cmc_{int(time.time())}_{random.randint(1000,9999)}"
    run_dir = os.path.join(output_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)
    
    print(f"   [CMCMF] Prep Run Dir: {run_dir}", flush=True)

    # Config.yaml
    config_data = {
        "api_key": API_KEY,
        "library_path": run_dir, # Write output here
        "output_file": "cmc_gen_base" # Basename
    }
    config_path = os.path.join(run_dir, "config.yaml")
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f)
        
    # Song Settings (The 4-Part Logic)
    # Parse instrument_id to integer if possible for GM
    try:
        inst_prog = int(instrument_id)
    except:
        inst_prog = 0 # Default Grand Piano

    song_settings = {
        "song_name": f"Encore_{base_name}",
        "tempo": "Andante", # dynamic later?
        "scale": "Major", # dynamic?
        "structure": [
            {
                "part_name": "Overture",
                "role": "Intro",
                "length_bars": 8,
                "description": f"A grand opening featuring the chosen instrument ({inst_prog}). Prompt: {prompt}",
                "instruments": [{"program": inst_prog, "role": "Lead"}]
            },
            {
                "part_name": "Chorus",
                "role": "Main",
                "length_bars": 16,
                "description": "The main thematic development. Emotional and virtuosic.",
                "instruments": [{"program": inst_prog, "role": "Lead"}, {"program": 48, "role": "Pad"}] # 48=Strings
            },
            {
                "part_name": "Return",
                "role": "Bridge",
                "length_bars": 8,
                "description": "A twisted variation of the overture. darker.",
                "instruments": [{"program": inst_prog, "role": "Lead"}]
            },
            {
                "part_name": "Coda",
                "role": "Outro",
                "length_bars": 8,
                "description": "A final flourish. Triumphant.",
                "instruments": [{"program": inst_prog, "role": "Lead"}]
            }
        ]
    }
    settings_path = os.path.join(run_dir, "song_settings.json")
    with open(settings_path, 'w') as f:
        json.dump(song_settings, f, indent=2)

    # 2. Generate Base MIDI
    print("\n[1/4] Generating Classical Base (CMC)...", flush=True)
    # Use subprocess to call song_generator OR import class?
    # CMC is designed as CLI usually. Let's try subprocess to keep env clean?
    # Or import. Import is faster.
    # Note: CMC might rely on relative paths or sys.argv.
    # Let's assume we can invoke a 'process' function if it exists.
    # Assuming standard behavior, we'll try to invoke the main function logic manually or clean subprocess.
    # Subprocess is safer for cwd issues.
    
    # We need to point python path to here
    env = os.environ.copy()
    env["PYTHONPATH"] = os.getcwd() # accessible
    
    # We need an entry point for CMC that takes args.
    # Since I don't know exact 'cmc_core' entry syntax yet, I'll write a small wrapper or just assume `python -m cmc_core.main` works?
    # Plan: Import here.
    
    # [!] CRITICAl: CMC needs to read the files we just wrote.
    # pass 'run_dir' to it?
    # Since I don't have the code for `song_generator.py` in front of me (it was 'temp_cmc'), I need to trust it works or View it.
    # Assuming I can Modify `cmc_core` to accept explicit paths.
    
    # Placeholder: I'll assume `cmc_core.generate(config_path, settings_path)` signature for now, 
    # but I will view the file in next step to confirm.
    
    # FOR NOW: Creating a dummy MIDI for testing pipeline if I can't run CMC yet?
    # No, I must use CMC.
    # I'll view `cmc_core` in the next turn to ensure integration.
    
    # ...
    # [Implementation continues in actual file write]
