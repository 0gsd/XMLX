"""
15010.py - Advanced Multi-Model Transcription Pipeline

This module implements a complex audio-to-midi-to-audio pipeline.
Key Features:
- 6-Stem Separation (Demucs htdemucs_6s).
- Specialized Transcription Models:
    - Piano: ByteDance (High Accuracy).
    - Bass: TorchCrepe (Monophonic Pitch Tracking).
    - Guitar/Other: Basic Pitch (Spotify).
- Logic: "Winner Selection" based on note density or user preference, creating a focused mix.

AGENT NOTE:
- This file uses multiple heavy ML models (TorchCrepe, BasicPitch, Demucs).
- Ensure GPU availability for performance, though CPU fallbacks exist.
"""
import argparse
import os
import sys
import subprocess
import shutil
import random
import torch
import numpy as np
import librosa
import mido
import xmlx
from pydub import AudioSegment

# Inference Libraries
from basic_pitch.inference import predict
from piano_transcription_inference import PianoTranscription, sample_rate
import torchcrepe

# Global Device Selection
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"DEBUG: Using Device: {device}", flush=True)

# --- Utilities ---

def set_midi_program(midi_path, program_number):
    """
    Sets the MIDI program (instrument) for all tracks in a MIDI file.
    Does NOT use channel 10 (drums).
    """
    if not os.path.exists(midi_path): return
    
    try:
        mid = mido.MidiFile(midi_path)
        new_mid = mido.MidiFile()
        new_mid.ticks_per_beat = mid.ticks_per_beat
        
        for i, track in enumerate(mid.tracks):
             new_track = mido.MidiTrack()
             
             # Insert Program Change at Start
             # Channel assignment: usually safe to stick to channel 0-8. 
             # Let's preserve original channels but force program change on them?
             # Or force everything to channel 0? 
             # Safe bet: Insert program_change(program=N) at t=0
             
             new_track.append(mido.Message('program_change', program=program_number, time=0))
             
             for msg in track:
                 # Filter out existing program changes to avoid conflict?
                 if msg.type == 'program_change':
                     continue
                 new_track.append(msg)
                 
             new_mid.tracks.append(new_track)
             
        new_mid.save(midi_path)
        print(f"   [MIDI] Set {os.path.basename(midi_path)} to Program {program_number}", flush=True)
        
    except Exception as e:
        print(f"   [!] Failed to set MIDI program: {e}", flush=True)

def normalize_lufs(input_path, output_path, lufs=-14.0):
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-af', f'loudnorm=I={lufs}:TP=-1.0:LRA=11',
        '-ar', '44100',
        output_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

def has_audio(file_path, threshold=0.001):
    if not os.path.exists(file_path): return False
    try:
        y, sr = librosa.load(file_path, sr=None, duration=30)
        rms = np.sqrt(np.mean(y**2))
        return rms > threshold
    except:
        return False

def count_notes(midi_path):
    """Returns total number of NoteOn events."""
    if not os.path.exists(midi_path): return 0
    try:
        mid = mido.MidiFile(midi_path)
        count = 0
        for track in mid.tracks:
            for msg in track:
                if msg.type == 'note_on' and msg.velocity > 0:
                    count += 1
        return count
    except:
        return 0

# --- Separation ---

def separate_6_stems(input_wav, output_dir):
    print(f"\n[1/7] Separating 6 Stems (Demucs)...", flush=True)
    # Demucs automatically detects CUDA availability
    cmd = [
        sys.executable, "-m", "demucs.separate",
        "-n", "htdemucs_6s",
        "--out", output_dir,
        "--device", device,
        input_wav
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    except subprocess.CalledProcessError as e:
        print(f"[!] Demucs Error: {e.stdout.decode() if e.stdout else 'No output'}", flush=True)
        if device == 'cuda':
             print("[!] Retrying on CPU...", flush=True)
             cmd[cmd.index('--device') + 1] = 'cpu'
             try:
                 subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
             except subprocess.CalledProcessError as e2:
                 print(f"[!] Demucs CPU Fallback Error: {e2.stdout.decode() if e2.stdout else 'No output'}", flush=True)
                 return None
        else:
            return None
    
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

# --- Transcription Logic ---

def transcribe_piano(audio_path, midi_path):
    # ByteDance Model
    print(f"   > Transcribing PIANO (ByteDance) on {device}...", flush=True)
    transcriptor = PianoTranscription(device=device) 
    audio, _ = librosa.load(audio_path, sr=sample_rate, mono=True)
    transcriptor.transcribe(audio, midi_path)

def transcribe_guitar(audio_path, midi_path, model_path):
    # Basic Pitch (Optimized for Guitar)
    print(f"   > Transcribing GUITAR (Basic Pitch)...", flush=True)
    # Basic Pitch doesn't expose explicit device param in 'predict' convenience function unfortunately
    # It attempts to use GPU if TF/CoreML are set up. With our CUDA base image, it *should* work if TF sees GPU.
    model_output, midi_data, note_events = predict(audio_path, model_path)
    midi_data.write(midi_path)

def transcribe_bass(audio_path, midi_path):
    # TorchCrepe (Monophonic, High Precision)
    print(f"   > Transcribing BASS (TorchCrepe) on {device}...", flush=True)
    
    # 1. Load Audio
    sr = 16000
    audio, _ = librosa.load(audio_path, sr=sr, mono=True)
    audio = torch.tensor(np.copy(audio))[None] # Add batch dim
    audio = audio.to(device) # Move to device
    
    # 2. Predict Pitch (Crepe)
    # hop_length of 10ms = 160 samples
    hop_length = 160 
    fmin = 30 # Low bass B0 is ~30Hz
    fmax = 500 # High bass
    model = 'tiny'
    
    # Get pitch and confidence
    pitch, confidence = torchcrepe.predict(
        audio, sr, hop_length, fmin, fmax, 
        model, batch_size=2048, device=device, return_periodicity=True
    )
    
    # 3. Convert f0/periodicity to MIDI
    # Simple thresholding
    conf_thresh = 0.5
    pitch = pitch.squeeze(0).cpu().numpy()
    confidence = confidence.squeeze(0).cpu().numpy()
    
    # Create MIDI file
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    
    # Tempo/Time conversion
    ticks_per_beat = 480
    tempo = 500000 # 120 bpm
    ticks_per_frame = int(10000 / (tempo / ticks_per_beat)) # 9.6 ticks
    
    current_note = None
    time_accum = 0
    
    for i in range(len(pitch)):
        f0 = pitch[i]
        conf = confidence[i]
        
        if conf > conf_thresh and f0 > 0:
            midi_note = int(round(librosa.hz_to_midi(f0)))
            
            if current_note != midi_note:
                # Note changed
                if current_note is not None:
                    # Off previous
                    track.append(mido.Message('note_off', note=current_note, velocity=0, time=time_accum))
                    time_accum = 0
                
                # On new
                track.append(mido.Message('note_on', note=midi_note, velocity=100, time=time_accum))
                time_accum = ticks_per_frame
                current_note = midi_note
            else:
                # Sustain
                time_accum += ticks_per_frame
        else:
            # Silence
            if current_note is not None:
                track.append(mido.Message('note_off', note=current_note, velocity=0, time=time_accum))
                time_accum = ticks_per_frame
                current_note = None
            else:
                time_accum += ticks_per_frame
                
    mid.save(midi_path)
    
def transcribe_generic(audio_path, midi_path, model_path):
    print(f"   > Transcribing GENERIC (Basic Pitch)...", flush=True)
    try:
        model_output, midi_data, note_events = predict(audio_path, model_path)
        midi_data.write(midi_path)
    except Exception as e:
        print(f"     [!] BasicPitch failed: {e}", flush=True)

# --- Synthesis ---
def synthesize_midi(midi_path, wav_path, soundfont):
    cmd = [
        'fluidsynth', '-ni', '-g', '1.0', '-F', wav_path, '-r', '44100',
        soundfont, midi_path
    ]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

# --- Main Pipeline ---

def pipeline_15010(input_wav, soundfont_path, output_wav, favorite_instrument=None):
    output_dir = os.path.dirname(output_wav)
    base_name = os.path.splitext(os.path.basename(input_wav))[0]
    xml_output = os.path.join(output_dir, f"{base_name}.xml")
    temp_demucs = os.path.join(output_dir, "temp_demucs_15010")
    
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

    print(f"--- Processing 15010.XMlX: {input_wav} ---", flush=True)
    print(f"--- Preference: {favorite_instrument} ---", flush=True)

    # 1. Scale/Transcode (Handled by caller/wrapper usually, but input is wav here)
    
    # 2. Separation
    stem_files = separate_6_stems(input_wav, temp_demucs)
    
    if not stem_files:
        print("[!] Separation failed. Aborting pipeline.", flush=True)
        return

    # Flatten Stems and Normalize Permissions
    for s_name, s_path in stem_files.items():
        if os.path.exists(s_path):
            new_path = os.path.join(output_dir, f"{base_name}_{s_name}.wav")
            if os.path.exists(new_path):
                try: os.remove(new_path)
                except: pass
            shutil.copyfile(s_path, new_path)
            try: os.chmod(new_path, 0o644)
            except: pass
            stem_files[s_name] = new_path # Update path to local copy
        
    # 2. Transcription
    print(f"\n[2/6] Transcribing stems to MIDI...", flush=True)
    
    stem_midi = {} # name -> midi_path
    stem_render = {} # name -> render_path
    
    for s_name in ['vocals', 'drums', 'bass', 'guitar', 'piano', 'other']:
        if s_name in stem_files and os.path.exists(stem_files[s_name]) and has_audio(stem_files[s_name]):
            # File already moved to output_dir in Loop 1.
            new_path = stem_files[s_name] 
            print(f"[OUTPUT] Stem ({s_name.capitalize()})|{new_path}", flush=True)

            midi_out = os.path.join(output_dir, f"{base_name}_{s_name}.mid")
            render_out = os.path.join(output_dir, f"{base_name}_{s_name}_synth.wav")
            
            # --- Transcribe ---
            try:
                if s_name == 'piano':
                    transcribe_piano(stem_files[s_name], midi_out)
                    set_midi_program(midi_out, 0) # Acoustic Grand
                elif s_name == 'guitar':
                    transcribe_guitar(stem_files[s_name], midi_out, bp_model)
                    set_midi_program(midi_out, 25) # Acoustic Guitar (Steel)
                elif s_name == 'bass':
                    transcribe_bass(stem_files[s_name], midi_out)
                    set_midi_program(midi_out, 33) # Electric Bass (Finger)
                else: # vocals, drums, other
                    # User requested NO transcription for these stems.
                    # We print the audio link (above) but skip MIDI generation.
                    print(f"   > Skipping MIDI for {s_name} (Audio Only)", flush=True)
                    continue 

                stem_midi[s_name] = midi_out
                try: os.chmod(midi_out, 0o644)
                except: pass
                print(f"[OUTPUT] MIDI ({s_name.capitalize()})|{midi_out}", flush=True)
            except Exception as e:
                print(f"   [!] Failed to transcribe {s_name}: {e}", flush=True)
                continue

            # --- Render ---
            try:
                synthesize_midi(midi_out, render_out, soundfont_path)
                try: os.chmod(render_out, 0o644)
                except: pass
                stem_render[s_name] = render_out
                print(f"[OUTPUT] Render ({s_name.capitalize()})|{render_out}", flush=True)
            except Exception as e:
                print(f"   [!] Failed to render {s_name}: {e}", flush=True)

        else:
            if s_name not in stem_files:
                pass # Stem didn't exist
            else:
                print(f"   > Skipping {s_name} (Silent)", flush=True)

    # 5. Selection Logic
    print(f"\n[3/7] Determining Most Important Instrument...", flush=True)
    candidates = ['piano', 'guitar', 'bass']
    scores = {}
    
    for c in candidates:
        if c in stem_midi:
            scores[c] = count_notes(stem_midi[c])
        else:
            scores[c] = 0
            
    print(f"   > Note Counts: {scores}", flush=True)
    
    winner = None
    
    # Check User Preference
    if favorite_instrument and favorite_instrument.lower() in candidates:
        fav = favorite_instrument.lower()
        if fav in stem_midi and scores[fav] > 0:
            print(f"   > USER PREFERENCE: {fav.upper()} verified ({scores[fav]} notes).", flush=True)
            winner = fav
        else:
            print(f"   > USER PREFERENCE: {fav.upper()} request failed (0 notes or missing). :(", flush=True)
            # Fail gracefully as requested? Or Fallback? 
            # User said: "fail gracefully with 'Sorry, your favorite didn't have enough notes, or any. :('"
            # We can print this. But we probably still want to produce a fallback mix or silence?
            print("   > Falling back to 'I Love Them All' logic (Max Notes).", flush=True)
            
    # Default / Fallback Algorithm (Max Notes)
    if not winner:
        # Filter candidates with > 0 notes
        valid_candidates = {k: v for k, v in scores.items() if v > 0}
        
        if valid_candidates:
            # Pick max
            winner = max(valid_candidates, key=valid_candidates.get)
            print(f"   > 'I LOVE THEM ALL' Selection: {winner.upper()} wins with {scores[winner]} notes.", flush=True)
        else:
            print("   [!] No significant notes found in ANY melodic stems.", flush=True)
            # Fallback hierarchy
            if 'vocals' in stem_files: winner = 'vocals'
            elif 'other' in stem_files: winner = 'other'
            elif 'piano' in stem_files: winner = 'piano' # Even if silent
            else: winner = 'other'
            print(f"   > Fallback Selection: {winner.upper()}", flush=True)
    
    print(f"   > WINNER: {winner.upper()}", flush=True)
    
    # 6. Normalization
    print(f"\n[4/7] Normalizing...", flush=True)
    
    norm_stems = {}
    for s_name, path in stem_files.items():
        norm_path = os.path.join(output_dir, f"{base_name}_{s_name}_norm.wav")
        normalize_lufs(path, norm_path)
        normalize_lufs(path, norm_path)
        try: os.chmod(norm_path, 0o644)
        except: pass
        norm_stems[s_name] = norm_path
        
    norm_renders = {}
    for s_name, path in stem_render.items():
        norm_path = os.path.join(output_dir, f"{base_name}_{s_name}_synth_norm.wav")
        normalize_lufs(path, norm_path)
        normalize_lufs(path, norm_path)
        try: os.chmod(norm_path, 0o644)
        except: pass
        norm_renders[s_name] = norm_path

    # 7. Final Mix (Winner Source + Winner Render)
    print(f"\n[5/7] Creating Final Mix ({winner.upper()} Only)...", flush=True)
    
    has_source = winner in norm_stems
    has_render = winner in norm_renders
    
    if has_source and has_render:
        try:
            s_source = AudioSegment.from_wav(norm_stems[winner])
            s_render = AudioSegment.from_wav(norm_renders[winner])
            
            # Mix
            mixed = s_source.overlay(s_render, position=0)
            mixed = mixed[:len(s_source)]
            mixed = mixed.normalize() - 6.0
            
            mixed.export(output_wav, format="wav")
            try: os.chmod(output_wav, 0o644)
            except: pass
            print(f"[OUTPUT] Winner Mix|{output_wav}", flush=True)
        except Exception as mx_err:
             print(f"   [!] Mix failed: {mx_err}", flush=True)
             # Fallback: Copy Source as Result
             subprocess.run(['cp', norm_stems[winner], output_wav], check=True)
             try: os.chmod(output_wav, 0o644)
             except: pass

    elif has_source:
        print("   [!] Winner has Source but no Render. Using Source.", flush=True)
        subprocess.run(['cp', norm_stems[winner], output_wav], check=True)
        try: os.chmod(output_wav, 0o644)
        except: pass
    else:
        print("   [!] Error: Winner stems missing for mix. Outputting silence.", flush=True)
        AudioSegment.silent(duration=1000).export(output_wav, format="wav")
        try: os.chmod(output_wav, 0o644)
        except: pass

    # 8. XML Generation
    print(f"\n[6/7] Generating XML...", flush=True)
    
    stems_data = {}
    
    for s_name in stem_files.keys():
        entry = {}
        if s_name in stem_files: entry['audio'] = stem_files[s_name]
        if s_name in stem_midi: entry['midi'] = stem_midi[s_name]
        if s_name in stem_render: entry['render'] = stem_render[s_name]
        
        stems_data[s_name] = entry
    
    xmlx.generate_xml(input_wav, xml_output, final_mix_path=output_wav, stems=stems_data)
    print("---------------------------------------------------", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("input_wav")
    parser.add_argument("soundfont")
    parser.add_argument("--output", "-o", default="out.wav")
    parser.add_argument("--favorite", "-f", default=None, help="Preferred instrument (piano, guitar, bass)")
    args = parser.parse_args()
    
    pipeline_15010(args.input_wav, args.soundfont, args.output, favorite_instrument=args.favorite)
