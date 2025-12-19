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
        
    # 3. Song Settings (Encore)
    try: inst_prog = int(instrument_id)
    except: inst_prog = 0
    
    inst_desc = "Piano" if inst_prog == 0 else "Instrument"
    
    song_settings = {
        "song_name": f"{base_name}",
        "tempo": "Andante" if inst_desc == "Piano" else "Adagio",
        "scale": "Minor", "genre": "Classical", "length": 32,
        "instruments": [ {"program_num": inst_prog, "role": "Lead", "name": "Soloist"} ],
        "theme_definitions": [
            {"label": "Overture", "role": "Intro", "description": f"Grand solo opening. Prompt: {prompt}", "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Soloist"}]},
            {"label": "Chorus", "role": "Main", "description": "Main thematic development. Virtuoso.", "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Soloist"}]},
            {"label": "Journey", "role": "Bridge", "description": "Experimental development.", "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Soloist"}]},
            {"label": "Coda", "role": "Outro", "description": "Triumphant flourish.", "instruments": [{"program_num": inst_prog, "role": "Lead", "name": "Soloist"}]}
        ]
    }
    with open(os.path.join(run_dir, "song_settings.json"), 'w') as f:
        json.dump(song_settings, f, indent=2)

    # 4. Invoke CMC (Subprocess)
    print("\n[1/3] Composing Encore...", flush=True)
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
    
    # Priority: Final
    final_candidates = [f for f in candidates if f.lower().startswith('final')]
    if final_candidates:
        base_midi = os.path.join(run_dir, final_candidates[0])
    else:
        # Fallback to combined or Stitch (Lazy stitching: just pick main part for now if CMC fails combine)
        # Actually CMC 'Final' usually works if 4 parts generated.
        base_midi = os.path.join(run_dir, sorted(candidates)[0]) if candidates else None

    if not base_midi:
        print("   [!] No MIDI generated. Aborting.", flush=True)
        return

    try: os.chmod(base_midi, 0o644)
    except: pass
    
    print(f"   [CMCMT] Selected MIDI: {os.path.basename(base_midi)}", flush=True)

    # 5b. Stitching (The Fix for Silence)
    print("\n[2.5/3] Stitching Parts (Robust)...", flush=True)
    final_midi_path = os.path.join(output_dir, f"{base_name}_final.mid")
    
    def stitch_midis_properly(run_dir, output_path, bars_per_part=32):
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
            print("   [!] No parts found to stitch!", flush=True)
            return False
            
        print(f"   [CMCMT] Found {len(parts)} parts: {parts}", flush=True)

        try:
            # 2. Setup Master based on first part
            first_part_path = os.path.join(run_dir, parts[0])
            first_mid = MidiFile(first_part_path)
            # Safe access to ticks_per_beat
            tpb = first_mid.tracks[0].ticks_per_beat if hasattr(first_mid.tracks[0], 'ticks_per_beat') else first_mid.ticks_per_beat
            
            master_midi = MidiFile(ticks_per_beat=tpb)
            # Init empty tracks based on first part structure
            for _ in first_mid.tracks:
                master_midi.tracks.append(MidiTrack())

            # Calculate Grid
            beats_per_bar = 4
            for msg in first_mid.tracks[0]:
                if msg.type == 'time_signature':
                    beats_per_bar = msg.numerator
                    break
            
            ticks_per_bar = tpb * beats_per_bar
            part_length_ticks = bars_per_part * ticks_per_bar
            
            current_start_tick = 0

            # 3. Stitch Loop
            for p_filename in parts:
                p_path = os.path.join(run_dir, p_filename)
                try:
                    mid = MidiFile(p_path)
                except:
                    print(f"      [!] Failed to read {p_filename}, skipping.")
                    continue

                # Append each track
                for t_idx, track in enumerate(mid.tracks):
                    if t_idx >= len(master_midi.tracks):
                        master_midi.tracks.append(MidiTrack())
                    
                    master_trk = master_midi.tracks[t_idx]
                    master_end_tick = sum(m.time for m in master_trk)
                    
                    # Gap calc
                    gap = current_start_tick - master_end_tick
                    if gap < 0: gap = 0 # Overlap protection
                    
                    first_event = True
                    for msg in track:
                        msg = msg.copy()
                        if first_event:
                            msg.time += gap
                            first_event = False
                        master_trk.append(msg)
                
                current_start_tick += part_length_ticks
            
            master_midi.save(output_path)
            print(f"   [CMCMT] Stitched {len(parts)} parts to {output_path}", flush=True)
            return True

        except Exception as e:
            print(f"   [!] Stitching failed: {e}", flush=True)
            import traceback
            traceback.print_exc()
            return False

    # Attempt Stitch
    if stitch_midis_properly(run_dir, final_midi_path, bars_per_part=32):
        base_midi = final_midi_path
    else:
        print("   [!] Stitching failed. Fallback to base MIDI.", flush=True)
        shutil.copyfile(base_midi, final_midi_path)
        
    try: os.chmod(final_midi_path, 0o644)
    except: pass
    
    # Update base_midi to point to the new evolved/remerged file
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
