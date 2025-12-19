
import os
import argparse
import subprocess
import shutil
import time
import xmlx # xmlx is still used for generate_xml
# requests and json removed as they were likely for MusicAiProcessor
# from utils import MusicAiProcessor removed (v3.67 simplification)

# --- Configuration ---
# MUSICAI_API_KEY removed as mastering logic is stripped
# MusicAiProcessor removed (v3.67 simplification)
WF_SLUG_P10NO = "p10nofinal" 

    # MusicAiProcessor definition moved to utils.py
            
# --- Main Logic ---

def pipeline_p10no(prompt, soundfont_path, output_xml_path):
    output_dir = os.path.dirname(output_xml_path)
    base_name = os.path.splitext(os.path.basename(output_xml_path))[0]
    
    # 0. Prep
    print(f"--- Processing P10NO.XMlX: {prompt} ---", flush=True)
    
    midi_path = os.path.join(output_dir, f"{base_name}_gen.mid")
    render_path = os.path.join(output_dir, f"{base_name}_render.wav")
    final_path = os.path.join(output_dir, f"{base_name}_final.wav")
    
    # 1. Generate MIDI (p10no.py)
    print("\n[1/4] Generating Composition (p10no)...", flush=True)
    cmd_gen = [
        'python3', 'p10no.py',
        '--prompt', prompt,
        '--duration', '3.0',
        '--output', midi_path
    ]
    subprocess.run(cmd_gen, check=True)
    # Copymode impossible here as created from scratch, but ensure perms
    try: os.chmod(midi_path, 0o666)
    except: pass
    
    
    # 2. Render MIDI (FluidSynth)
    print(f"\n[2/4] Rendering MIDI to Audio...", flush=True)
    cmd_synth = [
        'fluidsynth', '-ni', '-g', '1.0', '-F', render_path, '-r', '44100',
        soundfont_path, midi_path
    ]
    subprocess.run(cmd_synth, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try: os.chmod(render_path, 0o666)
    except: pass
    print(f"[OUTPUT] Render Draft|{render_path}", flush=True)

    # 3. Finalize (No Mastering)
    print(f"\n[3/4] Finalizing (Draft is Final)...", flush=True)
    if os.path.exists(final_path):
        try: os.remove(final_path)
        except: pass
    
    # Copy render to final
    subprocess.run(['cp', render_path, final_path], check=True)
    try: os.chmod(final_path, 0o666)
    except: pass
    print(f"[OUTPUT] Final Output|{final_path}", flush=True)

    # 4. XML Generation
    print(f"\n[4/4] Generating XML...", flush=True)
    stems_data = {
        'piano': {
            'midi': midi_path,
            'audio': final_path,
            'render': render_path
        }
    }
    # No 'input_wav' for XML gen since we made it from scratch. 
    # xmlx.generate_xml likely expects an input file for metadata. 
    # We'll pass the render_path as 'source' to satisfy signature.
    xmlx.generate_xml(render_path, output_xml_path, final_mix_path=final_path, stems=stems_data)
    print("---------------------------------------------------", flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    # Signature matching stream_process calls: script, input, font, output
    # But p10no has NO input file. stream_process might pass something dummy or we handle it.
    # We will assume main.py passes a dummy string or we make 'input_wav' optional/positional
    parser.add_argument("dummy_input", nargs='?', help="Ignored") 
    parser.add_argument("ignored_soundfont", nargs='?', help="Ignored legacy soundfont passed by stream_process") 
    parser.add_argument("--soundfont", required=True)
    parser.add_argument("--output", "-o", required=True)
    parser.add_argument("--prompt", default="Beautiful improvisation")
    
    args = parser.parse_args()
    
    # We use output filename to determine directories
    pipeline_p10no(args.prompt, args.soundfont, args.output.replace('.wav', '.xml')) 
    # Note: stream_process expects us to produce the file at 'output_path' argument.
    # We are producing an XML file? 
    # The 'output' arg from main is usually 'out.wav'. 
    # But for p10no, the main artifact is likely the XML + WAV.
    # Let's ensure we copy the final wav to args.output so stream processing 'finishes' correctly.
    
    final_wav = args.output
    # pipeline generates: ..._final.wav
    # We should copy that to args.output
    
    base = os.path.splitext(os.path.basename(args.output))[0]
    # Re-infer paths to copy result
    out_dir = os.path.dirname(args.output)
    gen_final = os.path.join(out_dir, f"{base}_final.wav")
    
    if os.path.exists(gen_final):
        subprocess.run(['cp', gen_final, final_wav], check=True)
        subprocess.call(['chmod', '777', final_wav])
