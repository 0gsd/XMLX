import argparse
"""
xYmix.py - YouTube/Video Output Module

Responsible for formatting audio mixes for video platforms (YouTube), potentially
handling video-specific transcoding or aspect ratio logic.
"""
import os
import sys
import os
import sys
import subprocess
import shutil
import tensorflow as tf
import torch
import numpy as np
import librosa
import mido
import pysynth
import traceback

from basic_pitch.inference import predict
from basic_pitch import ICASSP_2022_MODEL_PATH
from pydub import AudioSegment
import xmlx

# Inference Libraries (Matches xmiox.py)
try:
    from piano_transcription_inference import PianoTranscription, sample_rate
except ImportError:
    PianoTranscription = None
    sample_rate = 44100
import torchcrepe

def normalize_lufs(input_path, output_path, lufs=-14.0):
    """
    Normalizes audio to target LUFS using ffmpeg loudnorm filter.
    """
    cmd = [
        'ffmpeg', '-y',
        '-i', input_path,
        '-af', f'loudnorm=I={lufs}:TP=-1.0:LRA=11',
        '-ar', '44100',
        output_path
    ]
    # Suppress output unless error
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

# Global Device Selection
if torch.backends.mps.is_available():
    device = "mps"
elif torch.cuda.is_available():
    device = "cuda"
else:
    device = "cpu"
print(f"DEBUG: Using Device: {device}", flush=True)

# --- Transcription Helpers ---

def set_midi_program(midi_path, program_number):
    """
    Sets the MIDI program (instrument) for all tracks in a MIDI file.
    """
    if not os.path.exists(midi_path): return
    
    try:
        mid = mido.MidiFile(midi_path)
        new_mid = mido.MidiFile()
        new_mid.ticks_per_beat = mid.ticks_per_beat
        
        for i, track in enumerate(mid.tracks):
             new_track = mido.MidiTrack()
             new_track.append(mido.Message('program_change', program=int(program_number), time=0))
             for msg in track:
                 if msg.type == 'program_change': continue
                 new_track.append(msg)
             new_mid.tracks.append(new_track)
             
        new_mid.save(midi_path)
        print(f"   [MIDI] Set {os.path.basename(midi_path)} to Program {program_number}", flush=True)
    except Exception as e:
        print(f"   [!] Failed to set MIDI program: {e}", flush=True)


def transcribe_piano(audio_path, midi_path):
    print(f"   > Transcribing PIANO (ByteDance) on {device}...", flush=True)
    if not PianoTranscription:
        raise ImportError("PianoTranscription not installed")
    transcriptor = PianoTranscription(device=device) 
    audio, _ = librosa.load(audio_path, sr=sample_rate, mono=True)
    transcriptor.transcribe(audio, midi_path)

def transcribe_bass(audio_path, midi_path):
    print(f"   > Transcribing BASS (TorchCrepe) on {device}...", flush=True)
    sr = 16000
    audio, _ = librosa.load(audio_path, sr=sr, mono=True)
    audio = torch.tensor(np.copy(audio))[None].to(device)
    
    # Full Model
    pitch, confidence = torchcrepe.predict(
        audio, sr, 160, 30, 500, 'tiny', batch_size=2048, device=device, return_periodicity=True
    )
    
    pitch = pitch.squeeze(0).cpu().numpy()
    confidence = confidence.squeeze(0).cpu().numpy()
    
    mid = mido.MidiFile()
    track = mido.MidiTrack()
    mid.tracks.append(track)
    
    ticks_per_frame = 20 # Approx (10ms steps at 50/s? Standard MIDI logic needed)
    # crepe step size is 10ms (100Hz) by default
    # If 120bpm (500ms/beat) -> 480 ticks/beat -> 960 ticks/s => 10ms = 9.6 ticks.
    # Let's align with xmiox logic which used 20.
    
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
                time_accum = 20 
                current_note = midi_note
            else:
                time_accum += 20
        else:
            if current_note is not None:
                track.append(mido.Message('note_off', note=current_note, velocity=0, time=time_accum))
                time_accum = 20
                current_note = None
            else:
                time_accum += 20
                
    mid.save(midi_path)

def transcribe_generic(audio_path, midi_path, model_path, label="GENERIC"):
    print(f"   > Transcribing {label} (Basic Pitch)...", flush=True)
    try:
        predict(audio_path, model_path)[1].write(midi_path)
    except Exception as e:
        print(f"     [!] BasicPitch failed for {label}: {e}", flush=True)
        # Raise to allow fallback or handling
        raise e

def transcribe_and_mix(input_wav, soundfont_path, output_wav, preset=None):
    """
    1. Transcribes ANY audio to MIDI using Basic Pitch.
    2. Renders MIDI to WAV using FluidSynth (SF2) or PySynth (JSNTH).
    3. Mixes original and rendered WAVs.
    """
    
    # --- Configuration & Paths ---
    output_dir = os.path.dirname(output_wav)
    base_name = os.path.splitext(os.path.basename(input_wav))[0]
    
    midi_output = os.path.join(output_dir, f"{base_name}_xYmix.mid")
    synth_output = os.path.join(output_dir, f"{base_name}_xYmix_synth.wav")
    
    # ... (Copy Input logic handled in previous steps, safe to assume exists or caller ensures)
    # Re-verify copy logic since I'm replacing the function start
    import shutil
    input_copy = os.path.join(output_dir, os.path.basename(input_wav))
    if os.path.abspath(input_wav) != os.path.abspath(input_copy):
        shutil.copyfile(input_wav, input_copy)
        try: os.chmod(input_copy, 0o644)
        except: pass
        input_wav = input_copy
    
    # Path to the local model (Basic Pitch)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    # Updated: Points to /inf/icassp_2022/nmp.onnx relative to script in /app
    # If script is in /app, and inf is in /inf (root).
    # Then join(script_dir, '..', 'inf') -> /app/../inf -> /inf
    bp_model_dir = os.path.abspath(os.path.join(script_dir, '..', 'inf', 'icassp_2022', 'nmp.onnx'))

    print(f"--- Processing: {input_wav} ---", flush=True)
    
    # --- STEP 1: Transcription ---
    print("\n[1/3] Transcribing audio to MIDI...", flush=True)
    try:
        # Pysynth Preset ID mapping to Logic
        # JSNTH Presets: 'piano', 'guitar', 'bass', 'vocals', 'other', 'drums'
        # Note: preset arg is a string ID
        
        target_preset = preset if preset else 'piano'
        print(f"   > Method Selection for Preset '{target_preset}'...", flush=True)
        
        if target_preset == 'piano':
             transcribe_piano(input_wav, midi_output)
        elif target_preset == 'bass':
             transcribe_bass(input_wav, midi_output)
        elif target_preset == 'keys':
             transcribe_piano(input_wav, midi_output) # Use Piano model for keys
        else:
             # Guitar, Vocals, Drums, Other -> Basic Pitch
             transcribe_generic(input_wav, midi_output, bp_model_dir, label=target_preset.upper())

        try: os.chmod(midi_output, 0o644)
        except: pass
        print(f"   [✓] MIDI saved to: {midi_output}", flush=True)
        print(f"[OUTPUT] Transcription (MIDI)|{midi_output}", flush=True)

        if soundfont_path != 'JSNTH':
             try:
                # If preset is a numeric ID (0-127), apply it
                prog_id = int(target_preset)
                set_midi_program(midi_output, prog_id)
             except (ValueError, TypeError):
                # If preset is a string like 'piano', map to GM? 
                # For now, ignore string presets unless we want to map them.
                pass 

    except Exception as e:
        print(f"   [!] Error during transcription: {e}", flush=True)
        traceback.print_exc()
        return

    # --- STEP 2: Synthesis ---
    print("\n[2/3] Rendering MIDI to Audio...", flush=True)
    
    if soundfont_path == 'JSNTH':
         print(f"   > Using JSNTH Engine (Preset: {target_preset})...", flush=True)
         try:
             # Pysynth logic: render_to_file(midi_file, wav_file, preset_name)
             pysynth.render_to_file(midi_output, synth_output, target_preset)
             try: os.chmod(synth_output, 0o644)
             except: pass
             print(f"   [✓] Synthesized audio saved to: {synth_output}", flush=True)
         except Exception as e:
             print(f"   [!] JSNTH Failed: {e}", flush=True)
             traceback.print_exc()
             return
             
    else:
        # FluidSynth Logic
        if not os.path.exists(soundfont_path):
            print(f"   [!] Error: SoundFont file not found at: {soundfont_path}", flush=True)
            return

        try:
            cmd = [
                'fluidsynth', '-ni', '-g', '1.0', '-F', synth_output, '-r', '44100',
                soundfont_path, midi_output
            ]
            print(f"   [debug] Running: {' '.join(cmd)}", flush=True)
            subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            try: os.chmod(synth_output, 0o644)
            except: pass
            print(f"   [✓] Synthesized audio saved to: {synth_output}", flush=True)
            print(f"[OUTPUT] Synthesized Audio|{synth_output}", flush=True)

        except subprocess.CalledProcessError as e:
            print(f"   [!] FluidSynth Failed: {e.stdout.decode() if e.stdout else 'No output'}", flush=True)
            return
        except Exception as e:
            print(f"   [!] Error during synthesis: {e}", flush=True)
            return

    # --- STEP 3: Mixing & Export ---
    print("\n[3/3] Mixing Original and Synthesized Audio...", flush=True)
    
    try:
        # --- Normalization (LUFS) ---
        print("\n[3a/3] Normalizing components to -14 LUFS...", flush=True)
        norm_input = os.path.join(output_dir, f"{base_name}_norm_input.wav")
        norm_synth = os.path.join(output_dir, f"{base_name}_norm_synth.wav")

        normalize_lufs(input_wav, norm_input, lufs=-14)
        normalize_lufs(synth_output, norm_synth, lufs=-14)

        # --- Mixing ---
        print("\n[3b/3] Mixing and Finalizing...", flush=True)
        original_audio = AudioSegment.from_wav(norm_input)
        synth_audio = AudioSegment.from_wav(norm_synth)

        # Synchronization (Overlay at 0)
        mixed_audio = original_audio.overlay(synth_audio, position=0)

        # Trimming
        mixed_audio = mixed_audio[:len(original_audio)]

        # --- Final Peak Normalization to -6dB ---
        # Normalize to 0dB first, then reduce gain
        mixed_audio = mixed_audio.normalize() - 6.0 

        # Export
        if mixed_audio:
            mixed_audio.export(output_wav, format="wav")
            try: os.chmod(output_wav, 0o644)
            except: pass
            print(f"[OUTPUT] Mixed Audio|{output_wav}", flush=True)
        
        # Cleanup temp files
        # if os.path.exists(norm_input): os.remove(norm_input)
        # if os.path.exists(norm_synth): os.remove(norm_synth)
        
        print(f"\nSUCCESS! Final mixed file: {output_wav}", flush=True)
        print(f"[OUTPUT] Final Mix|{output_wav}", flush=True)

        # --- XML Generation ---
        xml_output = os.path.join(output_dir, f"{base_name}.xml")
        stems_data = {
            'MUSIC': {
                'midi': midi_output,
                'render': synth_output
            }
        }
        xmlx.generate_xml(input_wav, xml_output, final_mix_path=output_wav, stems=stems_data)
        try: os.chmod(xml_output, 0o644)
        except: pass
        print("---------------------------------------------------", flush=True)

    except Exception as e:
        print(f"   [!] Error during mixing: {e}", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe (Basic Pitch), Synthesize, and Mix Audio.")
    
    parser.add_argument("input_wav", help="Path to the source .wav file")
    parser.add_argument("soundfont", help="Path to the .sf2 SoundFont file")
    parser.add_argument("--output", "-o", default="final_xYmix.wav", help="Path for the final output file")
    parser.add_argument("--preset", "-p", default=None, help="Instrument Preset ID")
    args = parser.parse_args()
    
    if not os.path.exists(args.input_wav):
        print(f"Error: Input file '{args.input_wav}' does not exist.")
        sys.exit(1)

    transcribe_and_mix(args.input_wav, args.soundfont, args.output, preset=args.preset)
