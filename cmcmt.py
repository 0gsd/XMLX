import os
import argparse
import subprocess
import shutil
import time
import json
import yaml
import random
import sys
from pydub import AudioSegment

# --- Configuration ---
API_KEY = "AIzaSyCxRLtFM_ssb2rt19hxjoj58SDkF4Qdvdc"

def pipeline_cmcmt(prompt, instrument_id, output_wav_path, soundfont_path):
    """
    Project Cmcmt (v4.54): Robust rebuild of CMCMF (The Encore).
    """
    print(f"--- Project Cmcmt (Encore): {prompt} ---", flush=True)
    
    output_dir = os.path.dirname(output_wav_path)
    base_name = os.path.splitext(os.path.basename(output_wav_path))[0]
    
    # 1. Config Isolation
    run_id = f"cmcmt_{int(time.time())}_{random.randint(1000,9999)}"
    run_dir = os.path.join(output_dir, "temp_cmcmt_runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    print(f"   [CMCMT] Run Dir: {run_dir}", flush=True)

    # 2. Config.yaml
    config_data = {
        "api_key": API_KEY,
        "library_path": run_dir, 
        "model_name": "gemini-2.0-flash-exp",
        "output_file": base_name,
        "max_output_tokens": 32768,
        "enable_hotkeys": False
    }
    with open(os.path.join(run_dir, "config.yaml"), 'w') as f:
        yaml.dump(config_data, f)
        
    # 3. Song Settings (Encore - 9 Part Variation)
    try: inst_prog = int(instrument_id)
    except: inst_prog = 0
    
    inst_desc = "Piano" if inst_prog == 0 else "Instrument"
    
    # Define Themes (A, B, C)
    themes_map = {
        "A": {"label": "Theme A", "role": "Main", "description": f"Primary theme. Energetic and distinct. Prompt: {prompt}"},
        "B": {"label": "Theme B", "role": "Bridge", "description": "Contrasting theme. Slower, more melodic and expressive."},
        "C": {"label": "Theme C", "role": "Climax", "description": "Intense variation. Complex rhythm and higher dynamics."}
    }
    
    # Pattern: 1-2-1-2-3-2-2-3-1  -> A-B-A-B-C-B-B-C-A
    pattern = ["A", "B", "A", "B", "C", "B", "B", "C", "A"]
    
    theme_defs = []
    for idx, key in enumerate(pattern):
        base = themes_map[key]
        theme_defs.append({
            "label": f"{base['label']} (Var {idx+1})",
            "role": base['role'],
            "description": f"{base['description']} Variation {idx+1}.",
            "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Soloist"}]
        })

    song_settings = {
        "song_name": f"{base_name}",
        "tempo": "Allegro", 
        "scale": "Minor", "genre": "Classical", 
        "length": 8, # ~20 seconds at 100-120 BPM
        "instruments": [ {"program_num": inst_prog, "role": "Lead", "name": "Soloist"} ],
        "theme_definitions": theme_defs
    }
    
    with open(os.path.join(run_dir, "song_settings.json"), 'w') as f:
        json.dump(song_settings, f, indent=2)

    # 4. Invoke CMC (Subprocess)
    print("\n[1/3] Composing Encore (9 Variations)...", flush=True)
    CMC_CORE_DIR = os.path.join(os.path.dirname(__file__), "cmc_core")
    script_path = os.path.join(CMC_CORE_DIR, "song_generator.py")
    env = os.environ.copy()
    env["CMC_CONFIG_PATH"] = os.path.join(run_dir, "config.yaml")
    env["PYTHONPATH"] = os.path.dirname(CMC_CORE_DIR)

    cmd_cmc = ['python3', script_path, '--run', prompt]
    try:
        p = subprocess.Popen(
            cmd_cmc, cwd=run_dir, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1
        )
        if p.stdin:
            try: p.stdin.write("\n\n\n"); p.stdin.flush()
            except: pass
        for line in p.stdout:
            print(f"   [CMC] {line.strip()}", flush=True)
        p.wait()
    except Exception as e:
        print(f"   [!] Generation Failed: {e}", flush=True)
        return

    # 5. Find Output MIDI
    print("\n[2/3] Collecting MIDI...", flush=True)
    candidates = [f for f in os.listdir(run_dir) if f.endswith(".mid")]
    
    if not candidates:
        print("   [!] No MIDI generated. Aborting.", flush=True)
        return

    # 5b. Stitching (The Fix for Silence: Compact Stitching)
    print("\n[2.5/3] Stitching Parts (Compact)...", flush=True)
    final_midi_path = os.path.join(output_dir, f"{base_name}_final.mid")
    
    def stitch_midis_compact(run_dir, output_path):
        print(f"   [CMCMT] Stitching parts in {run_dir}...", flush=True)
        try:
            import mido
            from mido import MidiFile, MidiTrack
        except ImportError:
            print("   [!] mido not found. Cannot stitch.", flush=True)
            return False

        # 1. Gather Parts
        parts = [f for f in os.listdir(run_dir) if f.startswith('Part_') and f.endswith('.mid')]
        def get_part_num(name):
            try: return int(name.split('_')[1].split('.')[0])
            except: return 999
        parts.sort(key=get_part_num)

        if not parts:
            print("   [!] No parts found to stitch! Using fallback.", flush=True)
            return False
            
        print(f"   [CMCMT] Found {len(parts)} parts: {parts}", flush=True)

        try:
            # 2. Setup Master based on first part
            first_path = os.path.join(run_dir, parts[0])
            first_mid = MidiFile(first_path)
            tpb = first_mid.ticks_per_beat
            
            master_midi = MidiFile(ticks_per_beat=tpb)
            # Init empty tracks based on first part
            for _ in first_mid.tracks:
                master_midi.tracks.append(MidiTrack())

            # Grid Calc
            beats_per_bar = 4
            for msg in first_mid.tracks[0]:
                if msg.type == 'time_signature':
                    beats_per_bar = msg.numerator
                    break
            ticks_per_bar = tpb * beats_per_bar
            
            current_start_tick = 0

            # 3. Stitch Loop
            for p_filename in parts:
                p_path = os.path.join(run_dir, p_filename)
                try: mid = MidiFile(p_path)
                except: continue

                # Find length of this part (max tick)
                part_max_tick = 0
                for track in mid.tracks:
                    inputs_ticks = 0
                    for msg in track:
                        inputs_ticks += msg.time
                    if inputs_ticks > part_max_tick:
                        part_max_tick = inputs_ticks
                
                # Align to next bar
                import math
                bars = math.ceil(part_max_tick / ticks_per_bar)
                # Ensure at least 1 bar if empty?
                if bars < 1: bars = 1
                aligned_length = bars * ticks_per_bar
                
                # Append tracks
                for t_idx, track in enumerate(mid.tracks):
                    if t_idx >= len(master_midi.tracks):
                        master_midi.tracks.append(MidiTrack())
                    
                    master_trk = master_midi.tracks[t_idx]
                    master_end_tick = sum(m.time for m in master_trk)
                    
                    # Gap to current start
                    gap = current_start_tick - master_end_tick
                    if gap < 0: gap = 0
                    
                    first = True
                    for msg in track:
                        msg = msg.copy()
                        if first:
                            msg.time += gap
                            first = False
                        master_trk.append(msg)
                
                # Advance cursor (Sequential)
                current_start_tick += aligned_length
            
            master_midi.save(output_path)
            print(f"   [CMCMT] Stitched {len(parts)} parts to {output_path}", flush=True)
            return True

        except Exception as e:
            print(f"   [!] Stitching failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return False

    # Attempt Stitch
    if stitch_midis_compact(run_dir, final_midi_path):
        base_midi = final_midi_path
    else:
        # Fallback to whatever 'final' file exists or the first part
        final_candidates = [f for f in candidates if f.lower().startswith('final')]
        if final_candidates:
             base_midi = os.path.join(run_dir, final_candidates[0])
        else:
             base_midi = os.path.join(run_dir, sorted(candidates)[0])
        print(f"   [!] Stitching failed or no parts. Using {base_midi}", flush=True)
        shutil.copyfile(base_midi, final_midi_path)
        
    try: os.chmod(final_midi_path, 0o644)
    except: pass
    
    base_midi = final_midi_path

    # 6. Render & Sanitize
    print(f"\n[3/3] Rendering & Sanitizing...", flush=True)
    temp_synth_path = os.path.join(output_dir, f"{base_name}_temp.wav")
    
    try:
        cmd = [
            'fluidsynth', '-ni', '-g', '1.0', '-F', temp_synth_path, '-r', '44100',
            soundfont_path, base_midi
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        print("   [CMCMT] Sanitizing WAV (Copy Method)...", flush=True)
        if not os.path.exists(temp_synth_path): raise FileNotFoundError("Fluidsynth output missing")
        
        shutil.copyfile(temp_synth_path, output_wav_path)
        os.chmod(output_wav_path, 0o644)
        
        if os.path.exists(temp_synth_path): os.remove(temp_synth_path)
        print(f"[OUTPUT] Final Audio|{output_wav_path}", flush=True)

    except Exception as e:
        print(f"   [!] Render Failed: {e}", flush=True)
        if os.path.exists(temp_synth_path):
            shutil.move(temp_synth_path, output_wav_path)
            try: os.chmod(output_wav_path, 0o644)
            except: pass


if __name__ == "__main__":
    print("[DEBUG] cmcmt.py process started", flush=True)
    try:
        import traceback
        parser = argparse.ArgumentParser()
        # Match main.py signature
        parser.add_argument("input_wav", nargs="?", help="Ignored")
        parser.add_argument("legacy_sf", nargs="?", help="Ignored") # This is instrument ID for cmcmf?
        parser.add_argument("--soundfont", "-s", required=True)
        parser.add_argument("--output", "-o", required=True)
        parser.add_argument("--prompt", default="Encore")
        
        args = parser.parse_args()
        
        if not os.path.exists(args.soundfont):
            print(f"[ERROR] Soundfont missing: {args.soundfont}", flush=True)
            
        pipeline_cmcmt(args.prompt, args.input_wav, args.output, args.soundfont)

    except Exception as e:
        print(f"\n[FATAL ERROR] cmcmt.py crashed: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
