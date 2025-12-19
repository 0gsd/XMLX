
import os
import argparse
import subprocess
import shutil
import time
import requests
import json
import xmlx
import p20convolver
from utils import MusicAiProcessor

# --- Configuration ---
MUSICAI_API_KEY = "0b8c5b07-182e-4e47-a97d-34d023203a91"
WF_SLUG_P10NO = "p10nofinal" 

    # MusicAiProcessor definition moved to utils.py
            
# --- Main Logic ---

def pipeline_p20co(prompt, soundfont_path, output_xml_path):
    output_dir = os.path.dirname(output_xml_path)
    base_name = os.path.splitext(os.path.basename(output_xml_path))[0]
    
    # 0. Prep
    print(f"--- Processing P20CO.XMlX: {prompt} ---", flush=True)
    
    midi_gen_path = os.path.join(output_dir, f"{base_name}_gen.mid")
     # User asked for "-convolved" appended to original generated .mid file name
    midi_conv_path = os.path.join(output_dir, f"{base_name}_gen-convolved.mid")
    render_path = os.path.join(output_dir, f"{base_name}_render.wav")
    final_path = os.path.join(output_dir, f"{base_name}_final.wav")
    
    # 1. Generate Base MIDI (p10no.py)
    print("\n[1/5] Generating Base Composition (p10no)...", flush=True)
    cmd_gen = [
        'python3', 'p10no.py',
        '--prompt', prompt,
        '--duration', '3.0',
        '--output', midi_gen_path 
    ]
    subprocess.run(cmd_gen, check=True)
    try: os.chmod(midi_gen_path, 0o666)
    except: pass
    
    # 2. Convolve MIDI (p20convolver)
    print("\n[2/5] Convolving MIDI (Slowing & Decorating)...", flush=True)
    p20convolver.convolve_midi(midi_gen_path, midi_conv_path)
    try: os.chmod(midi_conv_path, 0o666)
    except: pass
    
    # 3. Render Convolved MIDI (FluidSynth)
    print(f"\n[3/5] Rendering Audio...", flush=True)
    # Using midi_conv_path
    cmd_synth = [
        'fluidsynth', '-ni', '-g', '1.0', '-F', render_path, '-r', '44100',
        soundfont_path, midi_conv_path
    ]
    subprocess.run(cmd_synth, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try: os.chmod(render_path, 0o666)
    except: pass
    print(f"[OUTPUT] Render Draft|{render_path}", flush=True)

    # 4. Master with Music.AI
    print(f"\n[4/5] Mastering (Music.AI P10NO Workflow)...", flush=True)
    try:
        # Validate Render
        if not os.path.exists(render_path) or os.path.getsize(render_path) < 1000:
             print("     [!] Rendered WAV is missing or too small. Skipping upload.", flush=True)
             raise Exception("Invalid audio render")

        proc = MusicAiProcessor(MUSICAI_API_KEY)
        ul_url = proc.upload(render_path)
        
        results = proc.run_p10no_job(ul_url)
        
        dl_url = results.get('Piano_AFUrl')
        if not dl_url:
            vals = list(results.values())
            if vals: dl_url = vals[0]
            
        if dl_url:
            print("     Downloading Final Master...", flush=True)
            proc.download_file(dl_url, final_path)
            try: os.chmod(final_path, 0o666)
            except: pass
            print(f"[OUTPUT] Final Master|{final_path}", flush=True)
        else:
            print("     [!] No output URL found. Using Render.", flush=True)
            if os.path.exists(final_path):
                try: os.remove(final_path)
                except: pass
            subprocess.run(['cp', render_path, final_path], check=True)
            try: os.chmod(final_path, 0o666)
            except: pass

    except Exception as e:
        print(f"     [!] API Error: {e}. Fallback to local render.", flush=True)
        if os.path.exists(final_path):
            try: os.remove(final_path)
            except: pass
        subprocess.run(['cp', render_path, final_path], check=True)
        try: os.chmod(final_path, 0o666)
        except: pass
        subprocess.call(['chmod', '777', final_path])

    # 5. XML Generation
    print(f"\n[5/5] Generating XML...", flush=True)
    stems_data = {
        'piano': {
            'midi': midi_conv_path, # Provide the convolved MIDI as main midi
            'audio': final_path,
            'render': render_path
        },
        'source_midi': { # Extra stem for original
             'midi': midi_gen_path
        }
    }
    xmlx.generate_xml(render_path, output_xml_path, final_mix_path=final_path, stems=stems_data)
    print("---------------------------------------------------", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("dummy_input", nargs='?', help="Ignored") 
    parser.add_argument("ignored_soundfont", nargs='?', help="Ignored") 
    parser.add_argument("--soundfont", required=True)
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--prompt", default="Beautiful improvisation")
    
    args = parser.parse_args()
    
    # We use output filename to determine directories
    pipeline_p20co(args.prompt, args.soundfont, args.output.replace('.wav', '.xml')) 
    
    final_wav = args.output
    base = os.path.splitext(os.path.basename(args.output))[0]
    out_dir = os.path.dirname(args.output)
    gen_final = os.path.join(out_dir, f"{base}_final.wav")
    
    if os.path.exists(gen_final):
        if os.path.exists(final_wav):
            try: os.remove(final_wav)
            except: pass
        subprocess.run(['cp', gen_final, final_wav], check=True)
        subprocess.call(['chmod', '777', final_wav])
