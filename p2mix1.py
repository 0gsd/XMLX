import argparse
"""
p2mix1.py - Legacy Separation Module

Older logic, mainly serving as a reference or fallback for 2-stem/4-stem separation logic.
Core pipeline has moved to `fina1.py`.
"""
import mido
import os
import sys
import subprocess
import torch
import librosa
from pydub import AudioSegment
from midi2audio import FluidSynth
from piano_transcription_inference import PianoTranscription, sample_rate
import xmlx

# Global Device Selection
device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"DEBUG: Using Device: {device}", flush=True)

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
    # Suppress output using run and checking exit code quietly if successful
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try: os.chmod(output_path, 0o644)
    except: pass

def transcribe_and_mix(input_wav, soundfont_path, output_wav):
    """
    1. Transcribes piano WAV to MIDI using AI (ByteDance Model).
    2. Renders MIDI to WAV using FluidSynth.
    3. Mixes original and rendered WAVs with precise sync.
    """

    # --- Configuration & Paths ---
    # Determine base name and output directory from the desired output_wav path
    output_dir = os.path.dirname(output_wav)
    base_name = os.path.splitext(os.path.basename(input_wav))[0]
    
    # MIDI and Synth output should probably go to the same folder as output_wav
    midi_output = os.path.join(output_dir, f"{base_name}_transcribed.mid")
    synth_output = os.path.join(output_dir, f"{base_name}_synth.wav")
    xml_output = os.path.join(output_dir, f"{base_name}.xml")
    
    # --- Global Fix: Copy Input to Output Dir for clean XML linking ---
    import shutil
    input_copy = os.path.join(output_dir, os.path.basename(input_wav))
    if os.path.abspath(input_wav) != os.path.abspath(input_copy):
        # Force remove destination if it exists (prevents permission errors on overwrite)
        if os.path.exists(input_copy):
            try: os.remove(input_copy)
            except: pass # If ownership prevents removal, copyfile below will try/fail, but this helps in most cases
            
        shutil.copyfile(input_wav, input_copy)
        try: os.chmod(input_copy, 0o644)
        except: pass
        input_wav = input_copy # Use the local copy for processing and XML references
    
    # Check for GPU (CUDA) to speed up transcription
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    
    # Unbuffered output for real-time progress tracking
    print(f"--- Processing: {input_wav} ---", flush=True)
    print(f"--- Device: {device.upper()} ---", flush=True)

    # --- STEP 1: AI Transcription ---
    print("\n[1/3] Transcribing audio to MIDI...", flush=True)
    try:
        # Load audio (automatically resamples to the model's required 32kHz)
        # Use librosa directly to avoid attribute error in library
        (audio, _) = librosa.load(input_wav, sr=sample_rate, mono=True)
        
        # Initialize the ByteDance transcription model
        # (Note: This will download the pre-trained model (~100MB) on the first run)
        transcriptor = PianoTranscription(device=device, checkpoint_path=None)
        
        # Transcribe: This detects Note On/Off and Velocity
        transcriptor.transcribe(audio, midi_output)
        try: os.chmod(midi_output, 0o644)
        except: pass
        print(f"   [✓] MIDI saved to: {midi_output}", flush=True)
        print(f"[OUTPUT] Transcription (MIDI)|{midi_output}", flush=True)

    except Exception as e:
        print(f"   [!] Error during transcription: {e}", flush=True)
        return

    # --- STEP 2: Synthesis (FluidSynth) ---
    print("\n[2/3] Rendering MIDI to Audio...", flush=True)
    
    if not os.path.exists(soundfont_path):
        print(f"   [!] Error: SoundFont file not found at: {soundfont_path}", flush=True)
        return

    try:
        # Render MIDI to WAV using direct subprocess call for better control over arguments
        # Usage: fluidsynth [options] [soundfonts] [midifiles]
        # We use -F to render to file, -ni for no interface
        cmd = [
            'fluidsynth',
            '-ni',
            '-g', '1.0',           # Gain
            '-F', synth_output,    # Output file
            '-r', '44100',         # Sample rate
            soundfont_path,        # SoundFont
            midi_output            # Input MIDI
        ]
        
        print(f"   [debug] Running: {' '.join(cmd)}", flush=True)
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        try: os.chmod(synth_output, 0o644)
        except: pass
        print(f"   [✓] Synthesized audio saved to: {synth_output}", flush=True)
        print(f"[OUTPUT] Synthesized Audio|{synth_output}", flush=True)

    except subprocess.CalledProcessError as e:
        print(f"   [!] Error during synthesis: FluidSynth failed. {e.stderr.decode()}", flush=True)
        return
    except FileNotFoundError:
        print("   [!] Error: 'fluidsynth' command not found. Please install FluidSynth.", flush=True)
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

        # Synchronization
        mixed_audio = original_audio.overlay(synth_audio, position=0)

        # Trimming
        mixed_audio = mixed_audio[:len(original_audio)]

        # --- Final Peak Normalization to -6dB ---
        mixed_audio = mixed_audio.normalize() - 6.0 

        # Export
        mixed_audio.export(output_wav, format="wav")
        try: os.chmod(output_wav, 0o644)
        except: pass
        
        # Ensure intermediates are also readable if referenced
        try:
             if os.path.exists(norm_input): os.chmod(norm_input, 0o644)
             if os.path.exists(norm_synth): os.chmod(norm_synth, 0o644)
        except: pass
        
        # Cleanup temp files
        # if os.path.exists(norm_input): os.remove(norm_input)
        # if os.path.exists(norm_synth): os.remove(norm_synth)
        
        print(f"\nSUCCESS! Final mixed file: {output_wav}", flush=True)
        print(f"[OUTPUT] Final Mix|{output_wav}", flush=True)
        
        # --- XML Generation ---
        stems_data = {
            'PIANO': {
                'midi': midi_output,
                'render': synth_output
            }
        }
        xmlx.generate_xml(input_wav, xml_output, final_mix_path=output_wav, stems=stems_data)
        
        print("---------------------------------------------------", flush=True)

    except Exception as e:
        print(f"   [!] Error during mixing: {e}. (Is FFmpeg installed?)", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Transcribe, Synthesize, and Mix Solo Piano Audio.")
    
    parser.add_argument("input_wav", help="Path to the source .wav file (solo piano)")
    # Accept legacy positional argument from main.py (which ignores it but passes it anyway)
    parser.add_argument("legacy_soundfont_arg", nargs="?", default=None, help="Ignored positional soundfont path")
    parser.add_argument("--soundfont", "-s", default=None, help="Path to the .sf2 SoundFont file")
    parser.add_argument("--output", "-o", default="final_mix.wav", help="Path for the final output file")

    args = parser.parse_args()

    if not os.path.exists(args.input_wav):
        print(f"Error: Input file '{args.input_wav}' does not exist.")
        sys.exit(1)
        
    # If no soundfont provided, use default logic elsewhere or require it? 
    # For now, if None, we might fail or default to 'GeneralUser-GS.sf2' relative.
    # But main.py will pass it.
    if not args.soundfont:
        # Fallback if run manually without flag
        if os.path.exists("GeneralUser-GS.sf2"):
            args.soundfont = "GeneralUser-GS.sf2"
        else:
            args.soundfont = "/app/GeneralUser-GS.sf2" # Best guess

    transcribe_and_mix(args.input_wav, args.soundfont, args.output)
