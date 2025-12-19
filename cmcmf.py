
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

def pipeline_cmcmf(prompt, instrument_id, output_xml_path, soundfont_path):
    output_dir = os.path.dirname(output_xml_path)
    base_name = os.path.splitext(os.path.basename(output_xml_path))[0]
    
    print(f"--- Processing CMCMF.XMlX (Encore): {prompt} ---", flush=True)

    # 1. Config Isolation (Unique Run Dir)
    run_id = f"cmc_{int(time.time())}_{random.randint(1000,9999)}"
    run_dir = os.path.join(output_dir, "temp_cmc_runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    
    print(f"   [CMCMF] Prep Run Dir: {run_dir}", flush=True)

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
        
    # 3. Song Settings (Encore Structure)
    # Parse instrument choice
    try:
        inst_prog = int(instrument_id)
    except:
        inst_prog = 0 # Default Grand Piano
        
    # Robust Program Name mapping could go here, but strictly we just need the program number
    # for the CMC generator prompt context if we want to be fancy, but CMC structure defines the program.
    
    # NOTE: song_generator.py expects 'theme_definitions' and top-level 'length'.
    # We shorten to 8 bars and 3 parts to avoid token exhaustion.
    
    # Determine instrument description for conditional tempo
    inst_desc = "Piano" if inst_prog == 0 else "Other Instrument" # Simple check for now
    
    # 4. Song Settings (Force Solo Mode)
    # We explicitly define the global instruments list to strictly limit the track count.
    song_settings = {
        "song_name": f"{base_name}",
        "tempo": "Andante" if inst_desc == "Piano" else "Adagio", # Slower start for solo?
        "scale": "Minor",
        "genre": "Classical", # Override default "Electronic"
        "length": 32, # 32 bars per section * 4 sections = 128 bars (~5 mins)
        "instruments": [ # GLOBAL INSTRUMENT LIST
             {"program_num": inst_prog, "role": "Lead", "name": "Soloist"}
        ],
        "theme_definitions": [
            {
                "label": "Overture",
                "role": "Intro",
                "description": f"A grand solo opening featuring the chosen instrument (Program {inst_prog}). Focused and melodic. Prompt: {prompt}",
                "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Soloist"}]
            },
            {
                "label": "Chorus",
                "role": "Main",
                "description": "The main thematic development. A complex, standalone solo performance showcasing the full range of the instrument.",
                "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Soloist"}] 
            },
            {
                "label": "Evolving Journey",
                "role": "Bridge",
                "description": "A complex development section. Experimental and evolving solo texture.",
                "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Soloist"}]
            },
            {
                "label": "Coda",
                "role": "Outro",
                "description": "A final flourish. The solo concludes triumphantly.",
                "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Soloist"}]
            }
        ]
    }
    
    # 4. Invoke CMC (song_generator.py)
    # ... (Logic continues unchanged usually, but we need to ensure soundfont usage in Render step)
    
    # ... [Skipping ahead to Main Block for Soundfont Logic] ...

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

    print(f"   [CMCMF] Found Base MIDI: {base_midi}", flush=True)

    # 6. P20CO Pipeline
    print("\n[2/4] Extending & Evolving (P20CO)...", flush=True)
    # Rename output to _final.mid for clarity and ensure it is in output_dir (flat)
    final_midi_path = os.path.join(output_dir, f"{base_name}_final.mid")
    
    p20convolver.convolve_midi(base_midi, final_midi_path)
    try: os.chmod(final_midi_path, 0o644)
    except: pass

    # Also copy the base MIDI (raw CMC output) to output_dir so it is accessible via flat download
    base_midi_flat = os.path.join(output_dir, f"{base_name}_base.mid")
    try:
        subprocess.run(['cp', base_midi, base_midi_flat], check=True)
        try: os.chmod(base_midi_flat, 0o644)
        except: pass
    except Exception as e:
        print(f"   [!] Could not flatten base MIDI: {e}", flush=True)
        base_midi_flat = base_midi # Fallback to original path (might fail download if nested)

    # 7. Render (Python Rewrite)
    print(f"\n[3/4] Rendering Audio (SF: {os.path.basename(soundfont_path)})...", flush=True)
    render_path = os.path.join(output_dir, f"{base_name}.wav")
    temp_synth_path = os.path.join(output_dir, f"{base_name}_temp_synth.wav")
    
    try:
        from pydub import AudioSegment
        cmd_synth = [
            'fluidsynth', '-ni', '-g', '1.0', '-F', temp_synth_path, '-r', '44100',
            soundfont_path, final_midi_path
        ]
        subprocess.run(cmd_synth, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        # Python Rewrite
        print("   [CMCMF] Rewriting WAV...", flush=True)
        if os.path.exists(temp_synth_path):
            audio = AudioSegment.from_wav(temp_synth_path)
            audio.export(render_path, format="wav")
            os.chmod(render_path, 0o644)
            os.remove(temp_synth_path)
    
    except Exception as e:
        print(f"   [!] Render Failed: {e}", flush=True)
        # Fallback
        if os.path.exists(temp_synth_path):
             import shutil
             if os.path.exists(render_path): os.remove(render_path)
             shutil.move(temp_synth_path, render_path)
    
    try: 
        os.chmod(render_path, 0o644)
    except Exception as e:
        print(f"   [!] CHMOD Failed: {e}", flush=True)

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
        'soloist': {
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
    parser.add_argument("dummy_input", nargs='?')
    parser.add_argument("soundfont_arg", nargs='?') 
    parser.add_argument("--soundfont", default=None) 
    parser.add_argument("--output", required=True)
    parser.add_argument("--instrument", default="0")
    parser.add_argument("--prompt", default="A classical masterpiece")
    
    args = parser.parse_args()
    
    # Resolve Soundfont (Priority: Kwarg > Positional > Default)
    # User requested to allow chosen soundfont instead of forcing GeneralUser
    sf_path = args.soundfont
    if not sf_path:
        sf_path = args.soundfont_arg
        
    if not sf_path or not os.path.exists(sf_path):
        # Fallback search for default
        default_sf = "GeneralUser-GS.sf2"
        if os.path.exists(default_sf):
            sf_path = os.path.abspath(default_sf)
        elif os.path.exists(os.path.join("soundfonts", default_sf)):
            sf_path = os.path.abspath(os.path.join("soundfonts", default_sf))
        else:
             sf_path = default_sf # Last ditch
             
    pipeline_cmcmf(args.prompt, args.instrument, args.output.replace('.wav', '.xml'), sf_path)

