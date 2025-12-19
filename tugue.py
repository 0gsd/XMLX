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

def normalize_midi_timestamps(input_path, output_path):
    """
    Normalization helper for Tugue's multi-part stitching.
    """
    try:
        import mido
        mid = mido.MidiFile(input_path)
        first_note_ticks = []
        for track in mid.tracks:
            curr_ticks = 0
            for msg in track:
                curr_ticks += msg.time
                if msg.type == 'note_on' and msg.velocity > 0:
                    first_note_ticks.append(curr_ticks)
                    break 
        
        if not first_note_ticks:
            shutil.copyfile(input_path, output_path)
            return

        global_offset = min(first_note_ticks)
        if global_offset <= 0:
            shutil.copyfile(input_path, output_path)
            return

        for track in mid.tracks:
            removed = 0
            for msg in track:
                if removed >= global_offset: break
                to_remove = min(msg.time, global_offset - removed)
                msg.time -= to_remove
                removed += to_remove
        mid.save(output_path)
    except Exception as e:
        print(f"   [WARN] Norm failed: {e}", flush=True)
        shutil.copyfile(input_path, output_path)

def pipeline_tugue(prompt, output_wav_path, soundfont_path):
    """
    Project Tugue (v4.54): Robust rebuild of Fugue.
    """
    print(f"--- Project Tugue: {prompt} ---", flush=True)
    
    output_dir = os.path.dirname(output_wav_path)
    base_name = os.path.splitext(os.path.basename(output_wav_path))[0]
    
    # 1. Config Isolation
    run_id = f"tugue_{int(time.time())}_{random.randint(1000,9999)}"
    run_dir = os.path.join(output_dir, "temp_tugue_runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    print(f"   [TUGUE] Run Dir: {run_dir}", flush=True)

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
        
    # 3. Instrument Selection (Fugue)
    inst_pool = [
        {"name": "Harpsichord", "prog": 6}, {"name": "Church Organ", "prog": 19},
        {"name": "Violin", "prog": 40}, {"name": "Cello", "prog": 42},
        {"name": "Oboe", "prog": 68}, {"name": "Bassoon", "prog": 70},
        {"name": "Flute", "prog": 73}, {"name": "Grand Piano", "prog": 0}
    ]
    selected_insts = random.sample(inst_pool, 2)
    inst_a, inst_b = selected_insts[0], selected_insts[1]
    
    # 4. Song Settings
    song_settings = {
        "song_name": f"{base_name}",
        "tempo": "Allegro", "scale": "Minor", "length": 32,
        "theme_definitions": [
            {
                "label": "Exposition", "role": "Intro",
                "description": f"Exposition. Voice 1 ({inst_a['name']}) subject. Voice 2 ({inst_b['name']}) answer. Voice 3 ({inst_a['name']}) bass. Prompt: {prompt}",
                "instruments": [
                    {"program": inst_a['prog'], "role": "Lead", "name": "Voice 1"},
                    {"program": inst_b['prog'], "role": "Counterpoint", "name": "Voice 2"},
                    {"program": inst_a['prog'], "role": "Bass", "name": "Voice 3"}
                ]
            },
            {
                "label": "Development", "role": "Main",
                "description": "Episode/Development. Modulating sequences.",
                "instruments": [
                    {"program": inst_a['prog'], "role": "Lead", "name": "Voice 1"},
                    {"program": inst_b['prog'], "role": "Counterpoint", "name": "Voice 2"},
                    {"program": inst_a['prog'], "role": "Bass", "name": "Voice 3"}
                ]
            },
            {
                "label": "Recapitulation", "role": "Outro",
                "description": "Recapitulation. Final subject entry.",
                "instruments": [
                    {"program": inst_a['prog'], "role": "Lead", "name": "Voice 1"},
                    {"program": inst_b['prog'], "role": "Counterpoint", "name": "Voice 2"},
                    {"program": inst_a['prog'], "role": "Bass", "name": "Voice 3"}
                ]
            }
        ]
    }
    with open(os.path.join(run_dir, "song_settings.json"), 'w') as f:
        json.dump(song_settings, f, indent=2)

    # 5. Invoke CMC (Subprocess)
    print("\n[1/3] Composing Fugue...", flush=True)
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

    # 6. Find Output MIDI (Combiner Logic)
    print("\n[2/3] Stitching MIDI Parts...", flush=True)
    candidates = [f for f in os.listdir(run_dir) if f.endswith(".mid")]
    
    # If CMC made a 'Final', use it
    final_candidates = [f for f in candidates if f.lower().startswith('final')]
    if final_candidates:
        final_midi_path = os.path.join(run_dir, final_candidates[0])
        print(f"   [TUGUE] Found Combined MIDI: {final_midi_path}", flush=True)
    else:
        # Stitch
        final_midi_path = os.path.join(output_dir, f"{base_name}_stitched.mid")
        
        try:
            from mido import MidiFile, MidiTrack
            parts = sorted([f for f in candidates if not f.lower().startswith('combined')])
            if not parts:
                raise Exception("No MIDI parts found!")
                
            print("   [TUGUE] Attempting Stitch...", flush=True)
            full_midi = MidiFile(ticks_per_beat=960)
            # Init tracks
            temp_first = MidiFile(os.path.join(run_dir, parts[0]))
            for t in temp_first.tracks: full_midi.tracks.append(MidiTrack())
            
            for part in parts:
                p_in = os.path.join(run_dir, part)
                p_norm = os.path.join(run_dir, f"{part}_norm.mid")
                normalize_midi_timestamps(p_in, p_norm)
                
                mid = MidiFile(p_norm)
                scale = full_midi.ticks_per_beat / mid.ticks_per_beat if mid.ticks_per_beat else 1.0
                
                # Simple Append Logic
                for i, track in enumerate(mid.tracks):
                    if i >= len(full_midi.tracks): break
                    # Append messages
                    for msg in track:
                        msg.time = int(msg.time * scale)
                        full_midi.tracks[i].append(msg)
                        
            full_midi.save(final_midi_path)
            print(f"   [TUGUE] Stitched to: {final_midi_path}", flush=True)
            
        except Exception as e:
            # PANIC FALLBACK: Use largest part
            print(f"   [!] Stitching Failed: {e}.", flush=True)
            
            if candidates:
                largest_part = max(candidates, key=lambda f: os.path.getsize(os.path.join(run_dir, f)))
                shutil.copyfile(os.path.join(run_dir, largest_part), final_midi_path)
                print(f"   [TUGUE] Fallback MIDI: {largest_part}", flush=True)
            else:
                print("   [!] No MIDI candidates to fallback on. Aborting.", flush=True)
                return

    try: os.chmod(final_midi_path, 0o644)
    except: pass

    # 7. Render & Sanitize
    print(f"\n[3/3] Rendering & Sanitizing...", flush=True)
    temp_synth_path = os.path.join(output_dir, f"{base_name}_temp.wav")
    
    try:
        cmd = [
            'fluidsynth', '-ni', '-g', '1.0', '-F', temp_synth_path, '-r', '44100',
            soundfont_path, final_midi_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        print("   [TUGUE] Sanitizing WAV (Copy Method)...", flush=True)
        if not os.path.exists(temp_synth_path): raise FileNotFoundError("No audio")
        
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
    print("[DEBUG] tugue.py process started", flush=True)
    try:
        import traceback
        parser = argparse.ArgumentParser()
        # Match main.py signature
        parser.add_argument("input_wav", nargs="?", help="Ignored")
        parser.add_argument("legacy_sf", nargs="?", help="Ignored")
        parser.add_argument("--soundfont", "-s", required=True)
        parser.add_argument("--output", "-o", required=True)
        parser.add_argument("--prompt", default="Baroque Fugue")
        
        args = parser.parse_args()
        
        print(f"[DEBUG] Soundfont Args: {args.soundfont}", flush=True)
        if not os.path.exists(args.soundfont):
            print(f"[ERROR] Soundfont file not found at: {args.soundfont}", flush=True)
            # Proceed anyway to see if fluidsynth complains or if checking is wrong
            
        pipeline_tugue(args.prompt, args.output, args.soundfont)
        
    except Exception as e:
        print(f"\n[FATAL ERROR] tugue.py crashed: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)
