
import os
import argparse
import subprocess
import shutil
import time
import json
import yaml
import random
import p20convolver

# --- Configuration ---
API_KEY = "AIzaSyCxRLtFM_ssb2rt19hxjoj58SDkF4Qdvdc"
SOUNDFONT_NAME = "GeneralUser-GS.sf2"
CMC_CORE_DIR = os.path.join(os.path.dirname(__file__), "cmc_core")

def pipeline_snata(prompt, output_xml_path):
    output_dir = os.path.dirname(output_xml_path)
    base_name = os.path.splitext(os.path.basename(output_xml_path))[0]
    
    # Force GeneralUser-GS
    script_dir = os.path.dirname(os.path.abspath(__file__))
    soundfont_path = os.path.join(script_dir, "GeneralUser-GS.sf2")
    if not os.path.exists(soundfont_path):
         # Try subdir or relative
         test_paths = [
             "GeneralUser-GS.sf2", "soundfonts/GeneralUser-GS.sf2",
             "/app/GeneralUser-GS.sf2"
         ]
         for t in test_paths:
             if os.path.exists(t):
                 soundfont_path = t
                 break
    
    print(f"--- Processing SNATA.XMlX: {prompt} ---", flush=True)

    # 1. Config Isolation (Unique Run Dir)
    run_id = f"snata_{int(time.time())}_{random.randint(1000,9999)}"
    run_dir = os.path.join(output_dir, "temp_snata_runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    
    print(f"   [SNATA] Run Dir: {run_dir}", flush=True)

    # 2. Config.yaml Generation
    # We point library_path to run_dir so outputs go there
    config_data = {
        "api_key": API_KEY,
        "library_path": run_dir, 
        "model_name": "gemini-2.0-flash-exp", # Fast & Good
        "output_file": base_name,
        "max_output_tokens": 32768,
        "enable_hotkeys": False # Disable for headless
    }
    config_path = os.path.join(run_dir, "config.yaml")
    with open(config_path, 'w') as f:
        yaml.dump(config_data, f)
        
    # 4. Song Settings (Sonata Structure)
    # Strict Solo Piano (Program 0)
    inst_prog = 0 
    
    song_settings = {
        "song_name": f"{base_name}",
        "tempo": "Allegro", # Typical 1st movement
        "scale": "Major", # Or dynamic? Let's stick to user intent or classic Sonata default
        "genre": "Classical",
        "length": 32, # 32 bars * 4 sections = 128 bars (~6 mins @ 80bpm, ~4m @ 120bpm). Let's do 4 sections.
        "instruments": [ 
             {"program_num": inst_prog, "role": "Lead", "name": "Solo Grand Piano"}
        ],
        "theme_definitions": [
            {
                "label": "Exposition",
                "role": "Intro",
                "description": f"Sonata Form: Exposition. A strong, declarative first subject in the tonic key, followed by a lyrical second subject in the dominant. Pure Solo Piano. Prompt: {prompt}",
                "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Solo Grand Piano"}]
            },
            {
                "label": "Development",
                "role": "Main",
                "description": "Sonata Form: Development. The themes are broken down, recombined, and modulated through various keys. High tension and virtuosity.",
                "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Solo Grand Piano"}] 
            },
            {
                "label": "Adagio",
                "role": "Bridge",
                "description": "A slow, expressive middle movement. Cantabile melody, rich harmony. Emotional and introspective.",
                "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Solo Grand Piano"}]
            },
            {
                "label": "Recapitulation",
                "role": "Outro",
                "description": "Sonata Form: Recapitulation (Rondo). The main themes return in the tonic key. A fast, energetic conclusion.",
                "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Solo Grand Piano"}]
            }
        ]
    }
    
    # Write settings
    settings_path = os.path.join(run_dir, "song_settings.json")
    with open(settings_path, 'w') as f:
        json.dump(song_settings, f, indent=2)

    # 4. Invoke CMC (song_generator.py)
    print("\n[1/4] Generating Classical Base (CMC)...", flush=True)
    
    script_path = os.path.join(CMC_CORE_DIR, "song_generator.py")
    
    env = os.environ.copy()
    env["CMC_CONFIG_PATH"] = config_path
    env["PYTHONPATH"] = os.path.dirname(CMC_CORE_DIR)

    cmd_cmc = ['python3', script_path, '--run', prompt]
    
    try:
        p = subprocess.Popen(
            cmd_cmc, 
            cwd=run_dir, 
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )
        if p.stdin:
            try:
                p.stdin.write("\n\n\n")
                p.stdin.flush()
            except: pass

        for line in p.stdout:
            print(f"   [CMC] {line.strip()}", flush=True)
            
        p.wait()
        
    except Exception as e:
        print(f"   [!] CMC Execution Error: {e}")
        try: p.kill() 
        except: pass
        
    # 5. Find Output MIDI
    # CMC output naming: {label}_{song_name}_{scale}_{length}bars_{bpm}_{timestamp}.mid
    # We want the "Final" combined midi if available.
    candidates = [f for f in os.listdir(run_dir) if f.endswith('.mid')]
    
    # Prioritize "Final" or "combined"
    final_candidates = [f for f in candidates if f.lower().startswith('final')]
    
    if final_candidates:
        base_midi = os.path.join(run_dir, final_candidates[0])
    elif candidates:
        base_midi = os.path.join(run_dir, candidates[0])
    else:
        print("   [!] No MIDI generated. Aborting.")
        import sys
        sys.exit(1)

    print(f"   [SNATA] Found Base MIDI: {base_midi}", flush=True)

    # 6. P20CO Pipeline
    print("\n[2/4] Extending & Evolving (P20CO)...", flush=True)
    # Rename output to _final.mid for clarity and ensure it is in output_dir (flat)
    # For Sonata, we reuse the CMC_CORE output as the base structure.
    # P20Convolver adds variation, but for pure piano sonata, maybe less is more?
    # User requested "interpolation/convolution", so we keep P20CO.
    final_midi_path = os.path.join(output_dir, f"{base_name}_final.mid")
    
    # Copy base to output too for reference
    base_midi_flat = os.path.join(output_dir, f"{base_name}_base.mid")
    try:
        # Use shell cp for safety
        subprocess.run(['cp', base_midi, base_midi_flat], check=True)
        try: os.chmod(base_midi_flat, 0o644)
        except: pass
    except: pass
    
    # Convolve
    p20convolver.convolve_midi(base_midi, final_midi_path)
    try: os.chmod(final_midi_path, 0o644)
    except: pass

    # 7. Render (Single Stem + Python Rewrite)
    # Goal: Use pydub to write the final file (fixes ownership/500 error) without the complexity/disk-usage of 2 stems.
    print(f"\n[3/4] Rendering Audio & Sanitizing...", flush=True)
    render_path = os.path.join(output_dir, f"{base_name}.wav")
    
    # Temp path for fluidsynth output
    temp_synth_path = os.path.join(output_dir, f"{base_name}_temp_synth.wav")
    
    try:
        from pydub import AudioSegment
        
        # 1. Render to TEMP
        cmd_synth = [
            'fluidsynth', '-ni', '-g', '1.0', '-F', temp_synth_path, '-r', '44100',
            soundfont_path, final_midi_path
        ]
        print(f"   [debug] Executing fluidsynth...", flush=True)
        subprocess.run(cmd_synth, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        # 2. Python Rewrite (The "Sanitizer")
        print("   [SNATA] Verifying and rewriting WAV...", flush=True)
        if not os.path.exists(temp_synth_path):
            raise FileNotFoundError(f"Fluidsynth failed to create {temp_synth_path}")
            
        audio = AudioSegment.from_wav(temp_synth_path)
        
        # Optional: Normalize?
        # audio = audio.normalize()
        
        # Export as final (Python writes this = Good Permissions)
        audio.export(render_path, format="wav")
        os.chmod(render_path, 0o644)
        
        # Cleanup
        if os.path.exists(temp_synth_path):
            os.remove(temp_synth_path)
            
    except Exception as e:
        print(f"   [!] Rendering Failed: {e}", flush=True)
        print(f"   [debug] Fallback: Moving temp file directly if exists.", flush=True)
        # Deep Failure Fallback: If pydub fails, just copy the file and pray chmod works
        import shutil
        if os.path.exists(temp_synth_path):
            if os.path.exists(render_path): os.remove(render_path)
            shutil.move(temp_synth_path, render_path)
            try: os.chmod(render_path, 0o644)
            except: pass
        else:
            # Panic: Write error to the WAV file so user sees it in browser (200 OK but text content)
            # Actually main.py handles the download, so we just ensure a file exists?
            # No, if we fail here, the file is missing and main.py 404s.
            print("   [CRITICAL] No audio file produced.", flush=True)

    if os.path.exists(render_path):
        st = os.stat(render_path)
        print(f"[DEBUG] Generated WAV Stats: Size={st.st_size} Mode={oct(st.st_mode)} UID={st.st_uid} GID={st.st_gid}", flush=True)
        if st.st_size == 0:
            print("   [!] WARNING: Generated WAV is 0 bytes!", flush=True)
    else:
        print("   [!] ERROR: WAV file was not created!", flush=True)

    print(f"[OUTPUT] Render Final|{render_path}", flush=True)

    # 8. XML
    print(f"\n[4/4] Generating XML...", flush=True)
    stems_data = {
        'sonata_piano': {
             'midi': final_midi_path,
             'audio': render_path
        },
        'base_structure': {'midi': base_midi_flat}
    }
    try:
        import xmlx
        xmlx.generate_xml(render_path, output_xml_path, final_mix_path=render_path, stems=stems_data)
        try: os.chmod(output_xml_path, 0o644)
        except: pass
    except:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Accept flexible args for main.py compatibility
    parser.add_argument("dummy_input", nargs='?', help="Ignored")
    parser.add_argument("dummy_sf", nargs='?', help="Ignored")
    parser.add_argument("--soundfont", default=None, help="Ignored") 
    
    parser.add_argument("--output", required=True)
    parser.add_argument("--prompt", default="A dynamic Piano Sonata")
    
    args = parser.parse_args()
             
    pipeline_snata(args.prompt, args.output.replace('.wav', '.xml'))

