
import os
import argparse
import subprocess
import shutil
import time
import json
import yaml
import random
import sys
import mido

# --- Configuration ---
# You might want to load this from env or shared config in a real app
API_KEY = "AIzaSyCxRLtFM_ssb2rt19hxjoj58SDkF4Qdvdc" # Hardcoded per cmcmf.py
SOUNDFONT_NAME = "GeneralUser-GS.sf2"
CMC_CORE_DIR = os.path.join(os.path.dirname(__file__), "cmc_core")



def normalize_midi_timestamps(input_path, output_path):
    """
    Reads a MIDI file, finds the timestamp of the first note event across all tracks,
    and shifts all tracks back by that amount. Removes leading silence.
    """
    try:
        mid = mido.MidiFile(input_path)
        
        # 1. Find global first note time
        first_note_ticks = []
        
        for track in mid.tracks:
            curr_ticks = 0
            for msg in track:
                curr_ticks += msg.time
                if msg.type == 'note_on' and msg.velocity > 0:
                    first_note_ticks.append(curr_ticks)
                    break # Found first note for this track
                    
        # If no notes found, just copy
        if not first_note_ticks:
            shutil.copyfile(input_path, output_path)
            return

        global_offset = min(first_note_ticks)
        
        if global_offset <= 0:
            shutil.copyfile(input_path, output_path)
            return

        # 2. Shift all tracks back by global_offset
        for track in mid.tracks:
            removed = 0
            for msg in track:
                if removed >= global_offset:
                    break
                
                # Calculate how much we can remove from this message
                to_remove = min(msg.time, global_offset - removed)
                msg.time -= to_remove
                removed += to_remove
        
        mid.save(output_path)
        
    except Exception as e:
        print(f"   [WARN] Normalization failed for {os.path.basename(input_path)}: {e}. Using original.", flush=True)
        shutil.copyfile(input_path, output_path)

def pipeline_fugue(prompt, output_wav_path, soundfont_path):
    output_dir = os.path.dirname(os.path.abspath(output_wav_path))
    base_name = os.path.splitext(os.path.basename(output_wav_path))[0]
    
    print(f"--- Generating Fugue: {prompt} ---", flush=True)

    # 1. Prep Run Dir
    run_id = f"fugue_{int(time.time())}_{random.randint(1000,9999)}"
    run_dir = os.path.join(output_dir, "temp_fugue_runs", run_id)
    os.makedirs(run_dir, exist_ok=True)
    print(f"   [FUGUE] Run Dir: {run_dir}", flush=True)

    # 2. Config.yaml for CMC
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
        
    # 3. Instrument Selection
    # "Baroque/Fugue Friendly" Pool
    # 6: Harpsichord, 19: Church Organ, 40: Violin, 42: Cello, 
    # 68: Oboe, 70: Bassoon, 73: Flute, 0: Grand Piano
    inst_pool = [
        {"name": "Harpsichord", "prog": 6},
        {"name": "Church Organ", "prog": 19},
        {"name": "Violin", "prog": 40},
        {"name": "Cello", "prog": 42},
        {"name": "Oboe", "prog": 68},
        {"name": "Bassoon", "prog": 70},
        {"name": "Flute", "prog": 73},
        {"name": "Grand Piano", "prog": 0}
    ]
    
    # Pick 2 distinct instruments
    selected_insts = random.sample(inst_pool, 2)
    inst_a = selected_insts[0]
    inst_b = selected_insts[1]
    
    print(f"   [FUGUE] Instruments: {inst_a['name']} (Voice 1/3) & {inst_b['name']} (Voice 2)", flush=True)

    # Voice Assignment:
    # Voice 1 (Soprano): Inst A
    # Voice 2 (Alto): Inst B
    # Voice 3 (Bass): Inst A (or maybe B? Let's go A to reinforce tonic)
    
    # 4. Song Settings (Fugue Structure)
    song_settings = {
        "song_name": f"{base_name}",
        "tempo": "Allegro", 
        "scale": "Minor", # Fugues sound cool in minor
        "length": 32, # 32 bars per section * 3 = 96 bars (~3-4 mins)
        "theme_definitions": [
            {
                "label": "Exposition",
                "role": "Intro",
                "description": f"Exposition. Voice 1 ({inst_a['name']}) introduces the Subject. Voice 2 ({inst_b['name']}) enters with the Answer. Voice 3 ({inst_a['name']}) enters with the Subject/Answer in the bass. Prompt: {prompt}",
                "instruments": [
                    {"program": inst_a['prog'], "role": "Lead", "name": "Voice 1 (Soprano)"},
                    {"program": inst_b['prog'], "role": "Counterpoint", "name": "Voice 2 (Alto)"},
                    {"program": inst_a['prog'], "role": "Bass", "name": "Voice 3 (Bass)"}
                ]
            },
            {
                "label": "Development",
                "role": "Main",
                "description": "Episode/Development. Modulating sequences, playful fragmentation of the subject.",
                "instruments": [
                    {"program": inst_a['prog'], "role": "Lead", "name": "Voice 1 (Soprano)"},
                    {"program": inst_b['prog'], "role": "Counterpoint", "name": "Voice 2 (Alto)"},
                    {"program": inst_a['prog'], "role": "Bass", "name": "Voice 3 (Bass)"}
                ]
            },
            {
                "label": "Recapitulation",
                "role": "Outro",
                "description": "Recapitulation. Final entry of the subject in the tonic key. Stretto sections. Majestic close.",
                "instruments": [
                    {"program": inst_a['prog'], "role": "Lead", "name": "Voice 1 (Soprano)"},
                    {"program": inst_b['prog'], "role": "Counterpoint", "name": "Voice 2 (Alto)"},
                    {"program": inst_a['prog'], "role": "Bass", "name": "Voice 3 (Bass)"}
                ]
            }
        ]
    }
    with open(os.path.join(run_dir, "song_settings.json"), 'w') as f:
        json.dump(song_settings, f, indent=2)

    # 5. Invoke CMC
    print("\n[1/2] Composing via CMC...", flush=True)
    env = os.environ.copy()
    env["CMC_CONFIG_PATH"] = os.path.join(run_dir, "config.yaml") # Point to isolated config
    
    cmd_cmc = [
        sys.executable,
        os.path.join(CMC_CORE_DIR, "song_generator.py"),
        "--run"
    ]
    
    try:
        # Capture stdout/stderr to debug 400 errors
        result = subprocess.run(
            cmd_cmc, 
            cwd=run_dir, 
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        print("   [CMC] Output:\n" + result.stdout, flush=True)
    except subprocess.CalledProcessError as e:
        print(f"\n[ERROR] CMC Failed with return code {e.returncode}", flush=True)
        print(f"--- STDOUT ---\n{e.stdout}\n", flush=True)
        print(f"--- STDERR ---\n{e.stderr}\n", flush=True)
        raise RuntimeError(f"CMC Generation execution failed: {e.stderr}")

    # 6. Find Output MIDI
    # CMC output naming: {label}_{song_name}_{scale}_{length}bars_{bpm}_{timestamp}.mid
    # We want the combined file or the parts?
    # CMC combines them into one MIDI file at the end usually if configured?
    # Actually song_generator.py outputs individual parts. We need to combine them or find the "Combined" file if it exists.
    # Wait, song_generator usually generates parts A, B, C...
    # We need to stitch them together or check if it made a full midi.
    # Looking at cmcmf.py, it uses p20convolver which takes ONE midi file.
    # Ah, song_generator creates a "Full_Song" midi? No, looking at logs it says "Successfully created MIDI file... A_Part...", "B_Part...", "C_Part..."
    # We need to concatenate these!
    # OR, we can just grab the parts and assume FluidSynth can render them? 
    # FluidSynth renders one MIDI file.
    # We need a quick concatenation script using music21 or mido.
    
    print("\n[2/2] Stitching & Rendering...", flush=True)
    
    midi_files = [f for f in os.listdir(run_dir) if f.endswith(".mid") and not f.startswith("combined")]
    midi_files.sort() # A_Part, B_Part, C_Part...
    
    if not midi_files:
        raise Exception("No MIDI files generated!")
        
    # Stitch using mido to merge tracks or append
    # Strategy: Normalize parts (remove leading silence/offsets) -> Stitch -> Render Stitched -> DONE.
    
    # import mido (Moved to top)
    from mido import MidiFile, MidiTrack, MetaMessage
    
    print("   [FUGUE] Stitching MIDI parts...", flush=True)
    full_midi = MidiFile(ticks_per_beat=960) # High res
    
    try:
        # Load all midis, Normalize them in memory or temp files first
        normalized_midis = []
        for f in midi_files:
            p_in = os.path.join(run_dir, f)
            p_norm = os.path.join(run_dir, f"{f}_norm.mid")
            normalize_midi_timestamps(p_in, p_norm)
            normalized_midis.append(MidiFile(p_norm))

        if not normalized_midis: raise Exception("No MIDI objects loaded")

        # Initialize tracks from first midi
        for t in normalized_midis[0].tracks:
            full_midi.tracks.append(MidiTrack())

        # Iterate parts
        for mid in normalized_midis:
            # 1. Calculate Max Length of THIS part
            scale = full_midi.ticks_per_beat / mid.ticks_per_beat if mid.ticks_per_beat else 1.0
            part_max_ticks = 0
            track_lengths = [] 

            for track in mid.tracks:
                t_ticks = 0
                for msg in track:
                    t_ticks += int(msg.time * scale)
                if t_ticks > part_max_ticks:
                    part_max_ticks = t_ticks
                track_lengths.append(t_ticks)

            # 2. Append messages + PAD
            for t_idx, track in enumerate(mid.tracks):
                if t_idx >= len(full_midi.tracks):
                    full_midi.tracks.append(MidiTrack())
                
                dest_track = full_midi.tracks[t_idx]
                
                # Append Events
                for msg in track:
                    new_msg = msg.copy()
                    new_msg.time = int(msg.time * scale)
                    dest_track.append(new_msg)
                
                # PAD
                padding = part_max_ticks - track_lengths[t_idx]
                if padding > 0:
                    dest_track.append(MetaMessage('marker', text='sync', time=padding))
                    
    except Exception as e:
        print(f"   [!] MIDI Stitching Failed: {e}", flush=True)
        # Fallback? No, we need this to work.
        
    # Save output midi (Stitched)
    try:
        out_mid_path = output_wav_path.replace(".wav", ".mid")
        full_midi.save(out_mid_path)
        try: os.chmod(out_mid_path, 0o644)
        except: pass
        print(f"[OUTPUT] Final MIDI|{out_mid_path}", flush=True)
    except Exception as e:
        print(f"   [!] MIDI Save Failed: {e}", flush=True)

    
    # 7. Rendering (Stitched MIDI) -> Python Rewrite
    # Replaces complex ffmpeg concat loop
    print(f"\n[2/2] Rendering Stitched Audio & Sanitizing...", flush=True)
    temp_synth_path = output_wav_path.replace(".wav", "_temp_synth.wav")
    
    try:
        from pydub import AudioSegment
        cmd_synth = [
            'fluidsynth',
            '-ni',
            soundfont_path,
            out_mid_path, 
            '-F', temp_synth_path,
            '-r', '44100',
            '-g', '1.0'
        ]
        subprocess.run(cmd_synth, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        
        # Python Rewrite
        print("   [FUGUE] Rewriting WAV for permissions...", flush=True)
        if os.path.exists(temp_synth_path):
            audio = AudioSegment.from_wav(temp_synth_path)
            audio.export(output_wav_path, format="wav")
            os.chmod(output_wav_path, 0o644)
            os.remove(temp_synth_path)
        else:
             print("   [!] Fluidsynth produced no file.", flush=True)

    except Exception as e:
        print(f"   [!] Rendering Failed: {e}", flush=True)
        # Fallback
        if os.path.exists(temp_synth_path):
             import shutil
             if os.path.exists(output_wav_path): os.remove(output_wav_path)
             shutil.move(temp_synth_path, output_wav_path)
             try: os.chmod(output_wav_path, 0o644)
             except: pass

    try: os.chmod(output_wav_path, 0o644)
    except: pass
    
    print(f"\n[OUTPUT] Final Fugue|{output_wav_path}", flush=True)

    # 8. XML Generation
    print(f"\n[3/3] Generating XML...", flush=True)
    xml_path = output_wav_path.replace(".wav", ".xml")
    
    # We fake "stems" by just providing the full mix and midi
    stems_data = {
        'fugue_mix': {
            'audio': output_wav_path,
            'midi': out_mid_path if os.path.exists(out_mid_path) else None
        }
    }
    
    try:
        import xmlx
        xmlx.generate_xml(output_wav_path, xml_path, final_mix_path=output_wav_path, stems=stems_data)
        try: os.chmod(xml_path, 0o644)
        except: pass
    except ImportError:
        print("   [!] Could not import xmlx.", flush=True)
    except Exception as e:
        print(f"   [!] XML Generation Failed: {e}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a 3-Part Fugue")
    # main.py passes [script, input_file, output_file, soundfont, ...]
    # But stream_process constructs: python script input_path soundfont ... --flags
    # So we need to accept input_path and soundfont as positionals even if we don't use them (or prefer kwargs)
    parser.add_argument("dummy_input", nargs='?', help="Positional input file (ignored)")
    parser.add_argument("soundfont_pos", nargs='?', help="Positional soundfont path (optional)")
    
    parser.add_argument("--prompt", required=True, help="Inspiration for the fugue")
    parser.add_argument("--output", required=True, help="Output WAV path")
    parser.add_argument("--soundfont", default=SOUNDFONT_NAME, help="Path to Soundfont")
    
    args = parser.parse_args()
    
    # Resolve SF path (Priority: Kwarg > Positional > Default)
    sf_path = args.soundfont
    if not sf_path or sf_path == SOUNDFONT_NAME:
        if args.soundfont_pos and args.soundfont_pos.endswith('.sf2'):
             sf_path = args.soundfont_pos

    if not os.path.exists(sf_path):
        # Locate locally if just filename
        potential = os.path.join(os.path.dirname(__file__), os.path.basename(sf_path))
        if os.path.exists(potential):
            sf_path = potential
        # Try finding in soundfonts dir
        potential_sf = os.path.join(os.path.dirname(__file__), "soundfonts", os.path.basename(sf_path))
        if os.path.exists(potential_sf):
            sf_path = potential_sf
            
    pipeline_fugue(args.prompt, args.output, sf_path)
