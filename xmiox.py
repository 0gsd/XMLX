import argparse
import os
import sys
import subprocess
import shutil
import torch
import numpy as np
import librosa
"""
xmiox.py - MIDI Input/Output Extensions

Handles MIDI processing logic, specifically bridging algorithmic composition tools
with standard MIDI file formats.
"""
import requests
import time
try:
    import musicai_sdk
except ImportError:
    musicai_sdk = None

import mido
import xmlx
import pysynth 
from pydub import AudioSegment

# Inference Libraries
from basic_pitch.inference import predict
from piano_transcription_inference import PianoTranscription, sample_rate
import torchcrepe

# Global Device Selection
if torch.backends.mps.is_available():
    device = "mps"
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"
print(f"DEBUG: Using Device: {device}", flush=True)

# --- Configuration (Clown Config) ---
MUSICAI_API_KEY = os.environ.get("MUSICAI_API_KEY", "0b8c5b07-182e-4e47-a97d-34d023203a91")
WF_SLUG_9STEM = "1in-9stems"

# Maps Stem Name -> GM Program Number (General MIDI)
CLOWN_MAP = {
    'vocals': 52,   # Choir Aahs (Fallback if vocals exist)
    'drums': 116,   # Taiko Drum
    'bass': 38,     # Synth Bass 1
    'guitar': 30,   # Distortion Guitar
    'piano': 0,     # Acoustic Grand
    'keys': 4,      # Electric Piano 1 (Rhodes)
    'other': 98     # Crystal
}

# --- Utilities ---

def normalize_lufs(input_path, output_path, lufs=-14.0):
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-af', f'loudnorm=I={lufs}:TP=-1.0:LRA=11',
        '-ar', '44100',
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def normalize_midi_timestamps(input_path, output_path=None):
    """
    Reads a MIDI file, finds the timestamp of the first note event across all tracks,
    and shifts all tracks back by that amount. Removes leading silence.
    If output_path is None, overwrites input_path.
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
                    
        # If no notes found, just copy/return
        if not first_note_ticks:
            if output_path and output_path != input_path:
                shutil.copyfile(input_path, output_path)
            return

        global_offset = min(first_note_ticks)
        
        if global_offset <= 0:
             if output_path and output_path != input_path:
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
        
        save_path = output_path if output_path else input_path
        mid.save(save_path)
        print(f"   [Sync] Normalized {os.path.basename(input_path)} (Shifted -{global_offset} ticks)", flush=True)
        
    except Exception as e:
        print(f"   [WARN] Normalization failed for {os.path.basename(input_path)}: {e}. Using original.", flush=True)
        if output_path and output_path != input_path and not os.path.exists(output_path):
            shutil.copyfile(input_path, output_path)

def inject_program_change(midi_path, program):
    """
    Injects a Program Change event at the start of the MIDI file 
    to ensure Fluidsynth uses the correct instrument.
    """
    try:
        mid = mido.MidiFile(midi_path)
        # Process all tracks? Usually track 0 or 1 has the setup.
        # Let's add it to the first track that has events or create one.
        
        # Simple strategy: clear existing program changes, insert new one at 0.
        for track in mid.tracks:
            # Filter out existing program_changes to avoid conflicts
            new_msgs = [msg for msg in track if msg.type != 'program_change']
            
            # Insert new one at start
            # We need to prepend. But 'time' is delta time.
            # So if first msg has time=100, and we insert one with time=0, it's fine.
            new_msgs.insert(0, mido.Message('program_change', program=program, time=0))
            
            # Replace track content (inplace sort of)
            track[:] = new_msgs
            
        mid.save(midi_path)
    except Exception as e:
        print(f"   [!] Failed to inject program change {program} into {midi_path}: {e}", flush=True)

# --- Separation ---

class MusicAiSeparator:
    def __init__(self, api_key):
        if not musicai_sdk:
             raise ImportError("musicai_sdk not installed")
        
        # Init Client
        if hasattr(musicai_sdk, 'MusicAiClient'):
             self.client = musicai_sdk.MusicAiClient(api_key=api_key)
        else:
             clients = [x for x in dir(musicai_sdk) if 'Client' in x]
             if clients:
                 self.client = getattr(musicai_sdk, clients[0])(api_key=api_key)
             else:
                 raise ImportError("MusicAiClient not found")

    def upload(self, file_path):
        print(f"   > Uploading {os.path.basename(file_path)}...", flush=True)
        if hasattr(self.client, 'upload_file'):
            return self.client.upload_file(file_path)
        raise NotImplementedError("Client has no upload_file")

    def run_9stem_job(self, input_url):
        print(f"   > Starting 1In-9Stems Job...", flush=True)
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                job = self.client.add_job(
                    job_name=f"XMIOX-9Stem-Try{attempt+1}",
                    workflow_slug=WF_SLUG_9STEM,
                    params={'inputUrl': input_url}
                )
                
                job_id = job.get('id') if isinstance(job, dict) else getattr(job, 'id')
                print(f"     Job ID: {job_id} (Attempt {attempt+1}/{max_retries}). Waiting...", flush=True)
                
                while True:
                    status = self.client.get_job(job_id)
                    if isinstance(status, dict):
                         s_str = status.get('status')
                         results = status.get('result') or status.get('outputs')
                         err_info = status.get('error')
                    else:
                         s_str = getattr(status, 'status', 'UNKNOWN')
                         results = getattr(status, 'result', {}) or getattr(status, 'outputs', {})
                         err_info = getattr(status, 'error', {})

                    if s_str == 'SUCCEEDED':
                        return results
                    elif s_str == 'FAILED':
                        print(f"     [!] Job Failed: {err_info}", flush=True)
                        break # Break inner while to trigger retry loop
                    time.sleep(5)
                    
            except Exception as e:
                print(f"     [!] Error starting/polling job: {e}", flush=True)
                time.sleep(2)
            
            # If we reached here (break from failed, or exception), retry
            if attempt < max_retries - 1:
                print(f"     Retrying job in 5 seconds...", flush=True)
                time.sleep(5)
            else:
                raise Exception(f"Job failed after {max_retries} attempts.")

    def download_stem(self, url, output_path):
        if os.path.exists(output_path):
            try: os.remove(output_path)
            except: pass
        r = requests.get(url)
        with open(output_path, 'wb') as f:
            f.write(r.content)
        # Ensure perms
        try: os.chmod(output_path, 0o666)
        except: pass

def separate_9_stems(input_wav, output_dir):
    print(f"\n[1/6] Separating 9 Stems (Music.AI)...", flush=True)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    sep = MusicAiSeparator(MUSICAI_API_KEY)
    
    # Extract basename for unique file naming
    base_name = os.path.splitext(os.path.basename(input_wav))[0]
    
    # 1. Upload
    url = sep.upload(input_wav)
    
    # 2. Run
    results = sep.run_9stem_job(url)
    
    # 3. Download & Map
    # Expected keys for 9-stem: 
    # 'bass', 'cymbals', 'hi_hat', 'keys', 'kick_drum', 'other', 'piano', 'snare_drum', 'toms'
    # 'vocals' is likely MISSING in 9-stem (Instrumental focus) or grouped in 'other'.
    
    stems_out = {}
    
    # Map API keys to local names
    # Note: API keys might be prefixed, e.g. 'Output9.kick_drum' or just 'kick_drum'
    key_targets = {
        'kick_drum': 'kick',
        'snare_drum': 'snare',
        'hi_hat': 'hi_hat',
        'cymbals': 'cymbals',
        'toms': 'toms',
        'bass': 'bass',
        'piano': 'piano',
        'keys': 'keys',
        'other': 'other'
    }
    
    if isinstance(results, dict):
        print(f"     [DEBUG] Job Result Keys: {list(results.keys())}", flush=True)
        for api_key, dl_url in results.items():
            # Check if any target key is part of the api_key
            matched_target = None
            for target_k, local_name in key_targets.items():
                if target_k in api_key: # substring match
                    matched_target = local_name
                    break
            
            if matched_target:
                # Use unique name: base_name_stem.wav
                out_path = os.path.join(output_dir, f"{base_name}_{matched_target}.wav")
                print(f"     Downloading {matched_target} (from {api_key})...", flush=True)
                try:
                    sep.download_stem(dl_url, out_path)
                    if os.path.exists(out_path):
                        stems_out[matched_target] = out_path
                except Exception as e:
                    print(f"     [!] Download failed for {api_key}: {e}", flush=True)
    
    return stems_out

# --- Transcription Logic ---

def transcribe_piano(audio_path, midi_path):
    print(f"   > Transcribing PIANO (ByteDance) on {device}...", flush=True)
    transcriptor = PianoTranscription(device=device) 
    audio, _ = librosa.load(audio_path, sr=sample_rate, mono=True)
    transcriptor.transcribe(audio, midi_path)

def transcribe_guitar(audio_path, midi_path, model_path):
    print(f"   > Transcribing GUITAR (Basic Pitch)...", flush=True)
    predict(audio_path, model_path)[1].write(midi_path)

def transcribe_bass(audio_path, midi_path):
    print(f"   > Transcribing BASS (TorchCrepe) on {device}...", flush=True)
    sr = 16000
    audio, _ = librosa.load(audio_path, sr=sr, mono=True)
    audio = torch.tensor(np.copy(audio))[None].to(device)
    
    pitch, confidence = torchcrepe.predict(
        audio, sr, 160, 30, 500, 'tiny', batch_size=2048, device=device, return_periodicity=True
    )
    
    pitch = pitch.squeeze(0).cpu().numpy()
    confidence = confidence.squeeze(0).cpu().numpy()
    
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    
    ticks_per_frame = 20 # Approx
    current_note = None
    time_accum = 0
    
    for i in range(len(pitch)):
        f0 = pitch[i]
        conf = confidence[i]
        
        if conf > 0.5 and f0 > 0:
            midi_note = int(round(librosa.hz_to_midi(f0)))
            if current_note != midi_note:
                if current_note is not None:
                    track.append(mido.Message('note_off', note=current_note, velocity=0, time=time_accum))
                    time_accum = 0
                track.append(mido.Message('note_on', note=midi_note, velocity=100, time=time_accum))
                time_accum = ticks_per_frame
                current_note = midi_note
            else:
                time_accum += ticks_per_frame
        else:
            if current_note is not None:
                track.append(mido.Message('note_off', note=current_note, velocity=0, time=time_accum))
                time_accum = ticks_per_frame
                current_note = None
            else:
                time_accum += ticks_per_frame
                
    mid.save(midi_path)

def transcribe_drums_from_stems(stem_paths, midi_out_path):
    print(f"   > Transcribing DRUMS (Piano Inference Model + Flattening)...", flush=True)
    master_track = mido.MidiTrack()
    mid = mido.MidiFile()
    mid.tracks.append(master_track)
    
    # We will collect ALL events into a single list then sort and write
    # List of (abs_time_ticks, type, note, velocity)
    all_events = []

    # Map stem name -> Target MIDI Note
    note_map = {
        'kick': 36,
        'snare': 38,
        'hi_hat': 42, # Closed HH
        'cymbals': 49, # Crash 1
        'toms': 47, # Low-Mid Tom
    }
    
    temp_dir = os.path.dirname(midi_out_path)

    for stem_name, audio_path in stem_paths.items():
        if stem_name not in note_map: continue
        target_note = note_map[stem_name]
        
        # Temp MIDI for this stem
        stem_temp_mid = os.path.join(temp_dir, f"temp_drum_{stem_name}.mid")
        
        try:
            # 1. Transcribe using robust Piano model
            transcribe_piano(audio_path, stem_temp_mid)
            
            # 2. Read back and Flatten
            if os.path.exists(stem_temp_mid):
                stem_mid_obj = mido.MidiFile(stem_temp_mid)
                
                # Assume Piano Transcription outputs Track 1 with notes (Track 0 is usually meta)
                # But we iterate all tracks to be safe
                for track in stem_mid_obj.tracks:
                    curr_ticks = 0
                    for msg in track:
                        curr_ticks += msg.time
                        if msg.type in ['note_on', 'note_off']:
                            # FLATTEN: Change pitch to target_note
                            # Keep velocity and time
                            all_events.append({
                                'time': curr_ticks,
                                'type': msg.type,
                                'note': target_note,
                                'velocity': msg.velocity
                            })
                
                # Cleanup temp
                try: os.remove(stem_temp_mid)
                except: pass
                
        except Exception as e:
             print(f"     [!] Failed to transcribe drum stem {stem_name}: {e}")

    # Sort events by absolute time
    all_events.sort(key=lambda x: x['time'])
    
    # Write to master track
    last_time = 0
    for evt in all_events:
        delta = evt['time'] - last_time
        if delta < 0: delta = 0 # Should not happen if sorted
        
        master_track.append(mido.Message(evt['type'], note=evt['note'], velocity=evt['velocity'], time=delta))
        last_time = evt['time']
        
    mid.save(midi_out_path)

def transcribe_generic(audio_path, midi_path, model_path, label="GENERIC"):
    print(f"   > Transcribing {label} (Basic Pitch)...", flush=True)
    try:
        predict(audio_path, model_path)[1].write(midi_path)
    except Exception as e:
        print(f"     [!] BasicPitch failed for {label}: {e}", flush=True)

# --- Synthesis ---

def synthesize_midi(midi_path, wav_path, soundfont):
    cmd = [
        'fluidsynth', '-ni', '-g', '2.0', # Boost gain for synthesis
        '-F', wav_path, '-r', '44100',
        soundfont, midi_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

# --- Merge ---

def merge_midi_files(stem_midi_map, output_mid):
    # Combine tracks from multiple MIDI files into one
    master = mido.MidiFile(type=1) # Type 1 = Multitrack
    
    # We assign channels to avoid collision? 
    # GM has 16 channels. Drums usually 10 (idx 9).
    # xmlynth uses mapped logic, but fluidsynth will respect channels/programs.
    
    channel_map = {
        'piano': 0,
        'bass': 1,
        'guitar': 2,
        'vocals': 3,
        'keys': 4,
        'other': 5,
        'drums': 9 # Standard percussion channel
    }

    for name, mid_path in stem_midi_map.items():
        try:
            mid = mido.MidiFile(mid_path)
            chan = channel_map.get(name, 6)
            
            for track in mid.tracks:
                # Clone track
                new_track = mido.MidiTrack()
                master.tracks.append(new_track)
                
                # Add Track Name meta event
                new_track.append(mido.MetaMessage('track_name', name=name.upper(), time=0))
                
                for msg in track:
                    # Modify channel if it's a channel message
                    if not msg.is_meta:
                        if hasattr(msg, 'channel'):
                            msg = msg.copy(channel=chan)
                    new_track.append(msg)
                    
        except Exception as e:
            print(f"Warning: Failed to merge MIDI {name}: {e}")
            
    master.save(output_mid)

# --- Main Pipeline ---

def pipeline_xmiox(input_wav, soundfont_path, output_wav):
    output_dir = os.path.dirname(output_wav)
    if not output_dir:
        output_dir = "."
    
    base_name = os.path.splitext(os.path.basename(input_wav))[0]
    xml_output = os.path.join(output_dir, f"{base_name}_xmiox.xml")
    
    # Copy Input
    input_copy = os.path.join(output_dir, os.path.basename(input_wav))
    if os.path.abspath(input_wav) != os.path.abspath(input_copy):
        if os.path.exists(input_copy):
            try: os.remove(input_copy)
            except: pass
        shutil.copyfile(input_wav, input_copy)

        try: os.chmod(input_copy, 0o644)
        except: pass
        input_wav = input_copy
        
    script_dir = os.path.dirname(os.path.abspath(__file__))
    bp_model = os.path.abspath(os.path.join(script_dir, '..', 'inf', 'icassp_2022', 'nmp.onnx'))

    print(f"--- Processing XMIOX (Clown's Mirror 2.85): {input_wav} ---", flush=True)

    # 1. Separation (9-Stem via Music.AI)
    # Replaces Demucs logic entirely
    # Expected keys: 'kick', 'snare', 'toms', 'hi_hat', 'cymbals', 'bass', 'piano', 'keys', 'other'
    stems_map = separate_9_stems(input_wav, output_dir)
    
    stem_files = {} # name -> wav_path
    stem_midi = {}  # name -> mid_path
    stem_render_raw = {} # name -> synth_wav_path
    
    # 2. Transcribe & Render
    print(f"\n[2/6] Doppelgänger Transformation (Transcribe + Synthesize)...", flush=True)
    
    # Define primary instrument groups for output
    # 'drums' will be a composite of kick/snare/toms/hats/cymbals
    groups = ['drums', 'bass', 'piano', 'keys', 'other']
    
    # A. Special handling for DRUMS component
    drum_stems = {k:v for k,v in stems_map.items() if k in ['kick', 'snare', 'toms', 'hi_hat', 'cymbals']}
    if drum_stems:
        midi_out = os.path.join(output_dir, f"{base_name}_drums_doppel.mid")
        render_out = os.path.join(output_dir, f"{base_name}_drums_doppel.wav")
        
        try:
            transcribe_drums_from_stems(drum_stems, midi_out)
            
            # Inject Program
            prog = CLOWN_MAP.get('drums', 116)
            if os.path.exists(midi_out):
                inject_program_change(midi_out, prog)
                try: os.chmod(midi_out, 0o644)
                except: pass
                # v4.03: Normalize Drums
                normalize_midi_timestamps(midi_out) 
                stem_midi['drums'] = midi_out
                stem_files['drums'] = drum_stems.get('kick') # Just use kick as representative audio? Or mix them? 
                # For XML, usually we want the full drum mix audio. 
                # Ideally we mix the 5 stems, but for now we might leave 'audio' empty or point to kick.
                
                # Render
                print(f"   > Synthesizing drums with PySynth Engine...", flush=True)
                pysynth.render_to_file(midi_out, render_out, 'drums')
                try: os.chmod(render_out, 0o644)
                except: pass
                stem_render_raw['drums'] = render_out
            else:
                 print(f"   [!] No drum MIDI produced.", flush=True)
        except Exception as e:
            print(f"   [!] Failed to process drums: {e}", flush=True)

    # B. Process Melodic Instruments
    for s_name in ['bass', 'piano', 'keys', 'other']:
        path = stems_map.get(s_name)
        if not path: continue
        
        path_final = path # It's already in output_dir
        stem_files[s_name] = path_final

        midi_out = os.path.join(output_dir, f"{base_name}_{s_name}_doppel.mid")
        render_out = os.path.join(output_dir, f"{base_name}_{s_name}_doppel.wav")
        
        try:
            # Transcribe
            # Transcribe - FORCED BYTEDANCE FOR ALL MELODIC STEMS (v3.40)
            # This ensures tighter timing alignment than BasicPitch/Crepe.
            if s_name in ['piano', 'keys', 'bass', 'other', 'vocals', 'guitar']:
                 transcribe_piano(path, midi_out)
            else:
                 # Fallback (though loop covers most)
                 transcribe_piano(path, midi_out)

            # Strict Timing Enforcement (v3.40)
            # Ensure MIDI track is exactly as long as source audio
            try:
                src_dur = librosa.get_duration(filename=path)
                mid = mido.MidiFile(midi_out)
                # Calculate current length
                mid_len = mid.length
                
                if mid_len < src_dur:
                    # Append silent event to extend track
                    # We need to add delta time to last track
                    # 120bpm = 0.5s/beat = 480 ticks. 
                    # Ticks per sec = 960 (approx logic used elsewhere)
                    # Mido uses ticks_per_beat.
                    
                    diff = src_dur - mid_len
                    # Just append a meta message at the end?
                    # Or a silent note off?
                    # Simplest: Just trust the player/renderer will play silence.
                    # But fluidsynth stops when MIDI stops. 
                    # So we need to PAD.
                    
                    # Convert diff seconds to ticks
                    # mid.ticks_per_beat (default 480). 
                    # Tempo default 120bpm -> 500000us/beat.
                    # seconds = ticks * (tempo_us / 1000000) / ticks_per_beat
                    # ticks = seconds * ticks_per_beat * 1000000 / tempo_us
                    
                    tempo_us = 500000 # Assume default 120bpm
                    ticks = int(diff * mid.ticks_per_beat * 1000000 / tempo_us)
                    
                    if ticks > 0 and len(mid.tracks) > 0:
                        mid.tracks[0].append(mido.MetaMessage('end_of_track', time=ticks))
                        mid.save(midi_out)
                        print(f"   [Time Align] Padded {s_name} by {diff:.2f}s", flush=True)
            except Exception as te:
                 print(f"   [Time Align] Warning: Could not enforce duration: {te}", flush=True)

            # Inject Program
            prog = CLOWN_MAP.get(s_name, 0)
            if os.path.exists(midi_out):
                inject_program_change(midi_out, prog)
                try: os.chmod(midi_out, 0o644)
                except: pass
                # v4.03: Normalize Stems
                normalize_midi_timestamps(midi_out) 
                stem_midi[s_name] = midi_out
            else:
                print(f"   [!] No MIDI produced for {s_name} (Silent?)", flush=True)
                continue

            # Render
            # Use FluidSynth (soundfont) for melodic instruments
            print(f"   > Synthesizing {s_name} with FluidSynth...", flush=True)
            synthesize_midi(midi_out, render_out, soundfont_path)
            
            try: os.chmod(render_out, 0o644)
            except: pass
            stem_render_raw[s_name] = render_out
            
        except Exception as e:
            print(f"   [!] Failed to transform {s_name}: {e}", flush=True)

    # 3. Optimize (Normalize)
    print(f"\n[3/6] Optimizing Doppelgängers (-6dB)...", flush=True)
    stem_render_opt = {} # name -> normalized_path
    
    for s_name, path in stem_render_raw.items():
        norm_path = os.path.join(output_dir, f"{base_name}_{s_name}_opt.wav")
        try:
            normalize_lufs(path, norm_path, lufs=-14.0) 
            stem_render_opt[s_name] = norm_path
            try: os.chmod(norm_path, 0o644)
            except: pass
            print(f"[OUTPUT] Render ({s_name.capitalize()})|{norm_path}", flush=True)
        except Exception as e:
            print(f"   [!] Failed to normalize {s_name}: {e}", flush=True)

    # 4. Merge MIDI
    print(f"\n[4/6] Merging MIDI Stems...", flush=True)
    full_midi_path = os.path.join(output_dir, f"{base_name}_full_arrangement.mid")
    merge_midi_files(stem_midi, full_midi_path)
    try: os.chmod(full_midi_path, 0o644)
    except: pass
    print(f"[OUTPUT] Full MIDI|{full_midi_path}", flush=True)

    # 5. Final Mix (Audio)
    print(f"\n[5/6] Mixing the Mirror...", flush=True)
    mixed = None
    
    for s_name, path in stem_render_opt.items():
        seg = AudioSegment.from_wav(path)
        if mixed is None:
            mixed = seg
        else:
            mixed = mixed.overlay(seg)
            
    if mixed:
        mixed.export(output_wav, format="wav")
        try: os.chmod(output_wav, 0o644)
        except: pass
        print(f"[OUTPUT] Mirror Mix|{output_wav}", flush=True)
    else:
        # Fallback (Synthesis failed for all stems)
        print("   [!] Synthesis failed. Generating Silent Fallback.", flush=True)
        AudioSegment.silent(duration=1000).export(output_wav, format="wav")
        try: os.chmod(output_wav, 0o644)
        except: pass
        print(f"[OUTPUT] Mirror Mix|{output_wav}", flush=True)

    # 6. XML Generation
    print(f"\n[6/6] Generating XML...", flush=True)
    
    stems_data = {}
    for s_name in groups:
        entry = {}
        if s_name in stem_files: entry['audio'] = stem_files[s_name]
        if s_name in stem_midi: entry['midi'] = stem_midi[s_name]
        if s_name in stem_render_opt: entry['render'] = stem_render_opt[s_name]
        
        stems_data[s_name] = entry
        
    xmlx.generate_xml(input_wav, xml_output, final_mix_path=output_wav, stems=stems_data)
    print(f"[OUTPUT] XML|{xml_output}", flush=True)
    print("---------------------------------------------------", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_wav")
    parser.add_argument("soundfont")
    parser.add_argument("--output", "-o", default="out.wav")
    # Accept extra args but ignore them (compatibility with main.py caller)
    parser.add_argument("--favorite", default=None) 
    args = parser.parse_args()
    
    try:
        pipeline_xmiox(args.input_wav, args.soundfont, args.output)
    except Exception as e:
        print(f"[CRITICAL] Pipeline crashed: {e}", flush=True)
        # Fallback: Copy input to output if possible
        if os.path.exists(args.input_wav):
            if args.input_wav != args.output:
                shutil.copyfile(args.input_wav, args.output)
                print(f"[OUTPUT] Fallback (Copy)|{args.output}", flush=True)
        else:
            # Create silent file
            AudioSegment.silent(duration=1000).export(args.output, format="wav")
            print(f"[OUTPUT] Fallback (Silence)|{args.output}", flush=True)
