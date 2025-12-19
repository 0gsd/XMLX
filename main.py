"""
main.py - Flask Backend Application

Routes requests, handles file uploads, and orchestrates calls to the various processing modules.
Key Responsibilities:
- Serving the `unified_index.html` frontend.
- Handling `/process/*` endpoints for different mixing algorithms.
- Managing temporary file storage in `/tmp` (Cloud Run compatible).
"""
import os
import subprocess
import sys
import json
import secrets
import shutil # v4.26
import traceback # v4.26
import uuid # v4.26
import io
import time
from flask import Flask, render_template, request, Response, jsonify, send_from_directory, send_file, session, after_this_request, stream_with_context
from werkzeug.utils import secure_filename
from google.oauth2 import id_token
from google.auth.transport import requests as google_requests
import mido

app = Flask(__name__)
# Ensure we have a secret key for session signing
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# --- Configuration ---
# ... (rest of config)
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')

# For Cloud Run (Linux), use /tmp/wavF. For Local (Mac/Win), use local wavF folder to be visible.
if sys.platform == "linux":
    WAV_F_FOLDER = '/tmp'
else:
    WAV_F_FOLDER = os.path.join(BASE_DIR, 'tmp_output')

SOUNDFONT_PATH = os.path.join(BASE_DIR, 'GeneralUser-GS.sf2')

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['WAV_F_FOLDER'] = WAV_F_FOLDER
app.config['SOUNDFONT_PATH'] = SOUNDFONT_PATH
app.config['MAX_CONTENT_LENGTH'] = 512 * 1024 * 1024  # 512 MB limit

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(WAV_F_FOLDER, exist_ok=True)

# --- Authentication Helpers ---
# Configure Base URL for Subprocesses (v4.46)
TIER = os.environ.get('TIER', 'PRO')
if TIER == 'PRO':
    os.environ['XMLX_BASE_URL'] = "https://pro.xmlx.app"
else:
    os.environ['XMLX_BASE_URL'] = "https://xmlx.app"
print(f"DEBUG: Configured XMLX_BASE_URL={os.environ['XMLX_BASE_URL']}", flush=True)

GOOGLE_CLIENT_ID = "382257788844-vddm3ltjtv58gvo880u825s7rammauji.apps.googleusercontent.com"

ALLOWED_USERS = os.environ.get('ALLOWED_USERS', '').split(',')
# Cleanup whitespace
ALLOWED_USERS = [u.strip() for u in ALLOWED_USERS if u.strip()]

def is_authorized():
    # Deprecated: Open Access v3.30
    return True

@app.route('/api/verify_token', methods=['POST'])
def verify_user_token():
    token = request.json.get('credential')
    if not token:
        return jsonify({'error': 'No token provided'}), 400

    try:
        # Verify token with Audience check
        id_info = id_token.verify_oauth2_token(token, google_requests.Request(), GOOGLE_CLIENT_ID)
        email = id_info.get('email')
        if email not in ALLOWED_USERS:
             return jsonify({'error': 'User not in allowlist', 'email': email}), 403

        # Success
        session['user_email'] = email
        return jsonify({'status': 'success', 'email': email})

    except ValueError as e:
        return jsonify({'error': str(e)}), 400

# --- SoundFolderFile Data ---
GM_PRESETS = [
    {"id":0,"name":"Acoustic Grand Piano"}, {"id":1,"name":"Bright Acoustic Piano"}, {"id":2,"name":"Electric Grand Piano"}, {"id":3,"name":"Honky-tonk Piano"},
    {"id":4,"name":"Electric Piano 1"}, {"id":5,"name":"Electric Piano 2"}, {"id":6,"name":"Harpsichord"}, {"id":7,"name":"Clavinet"},
    {"id":8,"name":"Celesta"}, {"id":9,"name":"Glockenspiel"}, {"id":10,"name":"Music Box"}, {"id":11,"name":"Vibraphone"},
    {"id":12,"name":"Marimba"}, {"id":13,"name":"Xylophone"}, {"id":14,"name":"Tubular Bells"}, {"id":15,"name":"Dulcimer"},
    {"id":16,"name":"Drawbar Organ"}, {"id":17,"name":"Percussive Organ"}, {"id":18,"name":"Rock Organ"}, {"id":19,"name":"Church Organ"},
    {"id":20,"name":"Reed Organ"}, {"id":21,"name":"Accordion"}, {"id":22,"name":"Harmonica"}, {"id":23,"name":"Tango Accordion"},
    {"id":24,"name":"Acoustic Guitar (nylon)"}, {"id":25,"name":"Acoustic Guitar (steel)"}, {"id":26,"name":"Electric Guitar (jazz)"}, {"id":27,"name":"Electric Guitar (clean)"},
    {"id":28,"name":"Electric Guitar (muted)"}, {"id":29,"name":"Overdriven Guitar"}, {"id":30,"name":"Distortion Guitar"}, {"id":31,"name":"Guitar harmonics"},
    {"id":32,"name":"Acoustic Bass"}, {"id":33,"name":"Electric Bass (finger)"}, {"id":34,"name":"Electric Bass (pick)"}, {"id":35,"name":"Fretless Bass"},
    {"id":36,"name":"Slap Bass 1"}, {"id":37,"name":"Slap Bass 2"}, {"id":38,"name":"Synth Bass 1"}, {"id":39,"name":"Synth Bass 2"},
    {"id":40,"name":"Violin"}, {"id":41,"name":"Viola"}, {"id":42,"name":"Cello"}, {"id":43,"name":"Contrabass"},
    {"id":44,"name":"Tremolo Strings"}, {"id":45,"name":"Pizzicato Strings"}, {"id":46,"name":"Orchestral Harp"}, {"id":47,"name":"Timpani"},
    {"id":48,"name":"String Ensemble 1"}, {"id":49,"name":"String Ensemble 2"}, {"id":50,"name":"SynthStrings 1"}, {"id":51,"name":"SynthStrings 2"},
    {"id":52,"name":"Choir Aahs"}, {"id":53,"name":"Voice Oohs"}, {"id":54,"name":"Synth Voice"}, {"id":55,"name":"Orchestra Hit"},
    {"id":56,"name":"Trumpet"}, {"id":57,"name":"Trombone"}, {"id":58,"name":"Tuba"}, {"id":59,"name":"Muted Trumpet"},
    {"id":60,"name":"French Horn"}, {"id":61,"name":"Brass Section"}, {"id":62,"name":"SynthBrass 1"}, {"id":63,"name":"SynthBrass 2"},
    {"id":64,"name":"Soprano Sax"}, {"id":65,"name":"Alto Sax"}, {"id":66,"name":"Tenor Sax"}, {"id":67,"name":"Baritone Sax"},
    {"id":68,"name":"Oboe"}, {"id":69,"name":"English Horn"}, {"id":70,"name":"Bassoon"}, {"id":71,"name":"Clarinet"},
    {"id":72,"name":"Piccolo"}, {"id":73,"name":"Flute"}, {"id":74,"name":"Recorder"}, {"id":75,"name":"Pan Flute"},
    {"id":76,"name":"Blown Bottle"}, {"id":77,"name":"Shakuhachi"}, {"id":78,"name":"Whistle"}, {"id":79,"name":"Ocarina"},
    {"id":80,"name":"Lead 1 (square)"}, {"id":81,"name":"Lead 2 (sawtooth)"}, {"id":82,"name":"Lead 3 (calliope)"}, {"id":83,"name":"Lead 4 (chiff)"},
    {"id":84,"name":"Lead 5 (charang)"}, {"id":85,"name":"Lead 6 (voice)"}, {"id":86,"name":"Lead 7 (fifths)"}, {"id":87,"name":"Lead 8 (bass + lead)"},
    {"id":88,"name":"Pad 1 (new age)"}, {"id":89,"name":"Pad 2 (warm)"}, {"id":90,"name":"Pad 3 (polysynth)"}, {"id":91,"name":"Pad 4 (choir)"},
    {"id":92,"name":"Pad 5 (bowed)"}, {"id":93,"name":"Pad 6 (metallic)"}, {"id":94,"name":"Pad 7 (halo)"}, {"id":95,"name":"Pad 8 (sweep)"},
    {"id":96,"name":"FX 1 (rain)"}, {"id":97,"name":"FX 2 (soundtrack)"}, {"id":98,"name":"FX 3 (crystal)"}, {"id":99,"name":"FX 4 (atmosphere)"},
    {"id":100,"name":"FX 5 (brightness)"}, {"id":101,"name":"FX 6 (goblins)"}, {"id":102,"name":"FX 7 (echoes)"}, {"id":103,"name":"FX 8 (sci-fi)"},
    {"id":104,"name":"Sitar"}, {"id":105,"name":"Banjo"}, {"id":106,"name":"Shamisen"}, {"id":107,"name":"Koto"},
    {"id":108,"name":"Kalimba"}, {"id":109,"name":"Bag pipe"}, {"id":110,"name":"Fiddle"}, {"id":111,"name":"Shanai"},
    {"id":112,"name":"Tinkle Bell"}, {"id":113,"name":"Agogo"}, {"id":114,"name":"Steel Drums"}, {"id":115,"name":"Woodblock"},
    {"id":116,"name":"Taiko Drum"}, {"id":117,"name":"Melodic Tom"}, {"id":118,"name":"Synth Drum"}, {"id":119,"name":"Reverse Cymbal"},
    {"id":120,"name":"Guitar Fret Noise"}, {"id":121,"name":"Breath Noise"}, {"id":122,"name":"Seashore"}, {"id":123,"name":"Bird Tweet"},
    {"id":124,"name":"Telephone Ring"}, {"id":125,"name":"Helicopter"}, {"id":126,"name":"Applause"}, {"id":127,"name":"Gunshot"}
]

# JSNTH Presets (mapped to pysynth strings)
JSNTH_PRESETS = [
    {"name": "Piano", "id": "piano"},
    {"name": "Guitar", "id": "guitar"},
    {"name": "Bass", "id": "bass"},
    {"name": "Vocals (Lead)", "id": "vocals"},
    {"name": "Strings", "id": "other"},
    {"name": "Drums", "id": "drums"},
]

def get_presets_data():
    """Scans for SF2 files and builds the preset map."""
    data = {}
    
    # Locations to scan: BASE_DIR and soundfonts subdirectory
    scan_dirs = [BASE_DIR, os.path.join(BASE_DIR, 'soundfonts')]
    
    sf2_files = set()
    for d in scan_dirs:
        if os.path.exists(d):
            for f in os.listdir(d):
                if f.lower().endswith('.sf2'):
                    # We store just the filename because main.py resolves it later?
                    # Wait, main.py resolution (line 358) assumes it's in 'soundfonts' OR we need logic.
                    # Current logic (line 358): os.path.join(BASE_DIR, 'soundfonts', os.path.basename(sf_rel_path))
                    # This implies valid SFs MUST be in 'soundfonts' dir for backend to find them.
                    # Dockerfile MOVES them to 'soundfonts' (lines 60, 65, etc).
                    # EXCEPT GeneralUser-GS.sf2 is in ROOT too.
                    # Let's trust that Dockerfile setup puts everything relevant into /app/soundfonts (except GeneralUser?).
                    # But line 33: SOUNDFONT_PATH = os.path.join(BASE_DIR, 'GeneralUser-GS.sf2').
                    # So we should support both.
                    sf2_files.add(f)
    
    # Sort
    sorted_sfs = sorted(list(sf2_files))
    
    # 1. Add SF2 entries (using GM Presets for now)
    for sf in sorted_sfs:
        data[sf] = GM_PRESETS
        
    # 2. Add JSNTH
    data["JSNTH"] = JSNTH_PRESETS
    
    return data

@app.route('/jsnth')
def jsnth_page():
    return render_template('jsnth.html')

@app.route('/')
def index():
    # Read ASCII Art (Single Layer Gradient)
    try:
        with open(os.path.join(BASE_DIR, 'xmlxappsci.txt'), 'r') as f:
            ascii_art = f.read()
    except FileNotFoundError:
        ascii_art = "XMlX.app"

    # Legacy Mask Logic Removed (v4.41)
    ascii_art_mask = ""

    tier = os.environ.get('TIER', 'PRO')
    try:
        presets_data = get_presets_data()
    except Exception as e:
        print(f"ERROR: get_presets_data failed: {e}", flush=True)
        presets_data = {}

    return render_template('unified_index.html', 
                         ascii_art=ascii_art, 
                         ascii_art_mask=ascii_art_mask,
                         tier=tier,
                         presets_data=presets_data)

@app.route('/api/ping')
def ping():
    """Helper for cross-tier visibility checks."""
    resp = jsonify({'status': 'pong', 'tier': os.environ.get('TIER', 'UNKNOWN')})
    # Allow CORS from anywhere (Free tier needs to hit this)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    resp.headers['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    resp.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return resp

def stream_process(script_name, input_path, output_path, soundfont_path=None, extra_args=None):
    """
    Helper generator to stream subprocess output for any script.
    """
    if soundfont_path is None:
        soundfont_path = SOUNDFONT_PATH

    cmd = [
        sys.executable, 
        os.path.join(BASE_DIR, script_name),
        input_path,
        soundfont_path,
        '--output', output_path
    ]
    
    if extra_args:
        cmd.extend(extra_args)
    
    yield f"data: {json.dumps({'log': f'Starting {script_name} with SF: {os.path.basename(soundfont_path)}...', 'step': 'Init'})}\n\n"

    # --- Transcoding Step ---
    if not input_path.lower().endswith('.wav'):
        yield f"data: {json.dumps({'log': 'Transcoding to WAV...', 'step': 'Transcoding'})}\n\n"
        wav_path = os.path.splitext(input_path)[0] + ".wav"
        
        cmd_ffmpeg = [
            'ffmpeg', '-y',
            '-i', input_path,
            '-vn',
            '-acodec', 'pcm_s16le',
            '-ar', '44100',
            '-ac', '2',
            wav_path
        ]
        
        try:
             subprocess.run(cmd_ffmpeg, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
             # Update input_path to use the new WAV for the subsequent script
             cmd[2] = wav_path
             
        except subprocess.CalledProcessError as e:
            yield f"data: {json.dumps({'error': f'Transcoding failed: {str(e)}'})}\n\n"
            return
        except Exception as e:
             yield f"data: {json.dumps({'error': f'Transcoding error: {str(e)}'})}\n\n"
             return

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1
        )

        for line in process.stdout:
            line = line.strip()
            if line:
                # Basic parsing to identify step for UI progress bar
                step = "Processing"
                if "Transcribing" in line or "[1/" in line: step = "Transcribing"
                if "Rendering" in line or "[2/" in line: step = "Rendering"
                if "Separating" in line: step = "Separating"
                if "Mixing" in line or "Combining" in line: step = "Mixing"
                
                if "[OUTPUT]" in line:
                    # Parse Structured Output: [OUTPUT] Label|/path/to/thing
                    try:
                        _, content = line.split("[OUTPUT]", 1)
                        label, fpath = content.strip().split("|", 1)
                        
                        # Verify it's within WAV_F_FOLDER or relative
                        # Use relpath to handle subdirectories (e.g. temp_demucs/...)
                        try:
                            rel_path = os.path.relpath(fpath, app.config['WAV_F_FOLDER'])
                            # quote path to handle spaces etc
                            from urllib.parse import quote
                            durl = f"/download/{quote(rel_path)}"
                        except ValueError:
                            # Fallback if path is weird
                            durl = f"/download/{os.path.basename(fpath)}"
                        
                        link_msg = json.dumps({
                            'link': {
                                'label': label,
                                'url': durl
                            }
                        })
                        #   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _   _
                        #  / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \ / \
                        # ( L | i | g | n | . | D | e | v |   | A | u | d | i | o |   | )
                        #  \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/ \_/
                        #   | | | | | | |  __/ | | | | | | (__| |_| |  __/ | | 
                        #   |_| |_|_| |_|\___| |_| |_| |_|\___|\___/ \___|_| |_|
                        #                                       v3.21
                        #   (c) 2025 Lign.Dev - All Rights Reserved
                        yield f"data: {link_msg}\n\n"
                    except:
                        pass # Ignore parsing errors for now
                
                msg = json.dumps({'log': line, 'step': step})
                yield f"data: {msg}\n\n"

        process.wait()
        
        if process.returncode == 0:
             final_msg = json.dumps({
                 'log': f"Process Completed.", 
                 'step': 'Done', 
                 'done': True, 
                 # 'path': output_path, # No longer needing single path
                 # 'url': ... # No longer auto-downloading single file
             })
             yield f"data: {final_msg}\n\n"
        else:
             error_msg = json.dumps({'log': "Process failed.", 'step': 'Error', 'error': True})
             yield f"data: {error_msg}\n\n"

    except Exception as e:
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

# --- API Endpoints ---

@app.route('/api/upload_chunk', methods=['POST'])
def upload_chunk():
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    file = request.files['file']
    filename = secure_filename(request.form['filename'])
    chunk_index = int(request.form['chunkIndex'])
    total_chunks = int(request.form['totalChunks'])
    
    # We use a temporary file to append chunks
    temp_path = os.path.join(app.config['UPLOAD_FOLDER'], f"{filename}.part")
    
    # If first chunk, ensure we start fresh (or could be RESUME logic, but let's keep it simple: truncate if index 0)
    mode = 'ab'
    if chunk_index == 0:
        mode = 'wb'
        
    with open(temp_path, mode) as f:
        f.write(file.read())
        
    # If last chunk, rename to final
    if chunk_index == total_chunks - 1:
        final_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        if os.path.exists(final_path):
             os.remove(final_path)
        os.rename(temp_path, final_path)
        return jsonify({'status': 'done', 'path': final_path})
        
    return jsonify({'status': 'chunk_received'})

@app.route('/api/process/<tool_type>', methods=['POST'])
def process_tool(tool_type):
    # --- PRO TIER LOCK ---
    tier = os.environ.get('TIER', 'PRO')
    PRO_TOOLS = ["fugue", "cmcmf", "fimai", "snata"]
    if tier != 'PRO' and tool_type in PRO_TOOLS:
        return jsonify({'error': 'This tool is reserved for PRO tier users.'}), 403
    
    filename = None
    
    # Check if this is a pre-uploaded file (via chunking) or a direct upload
    # 1. Generative Tools (Priority: Ignore uploaded filename if present)
    if tool_type in ['p10no', 'p20co', 'cmcmf', 'fugue', 'snata']:
         # Generative/Internal Tools: No input file needed
         # Use UUID to prevent collision
         import uuid
         filename = f"{tool_type}_{uuid.uuid4().hex[:8]}.wav"
         input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
         
         # --- FIX: Create Dummy File ---
         # Ensure input_path exists so subprocess/ffmpeg logic doesn't crash on FileNotFoundError
         try:
             with open(input_path, 'wb') as f:
                 f.write(b'DUMMY_HEADER') # Write minimal bytes
             print(f"DEBUG: Created dummy input file: {input_path}", flush=True)
         except Exception as e:
             print(f"ERROR: Failed to create dummy input: {e}", flush=True)

    # 2. Check if this is a pre-uploaded file (via chunking)
    elif 'filename' in request.form:
         filename = secure_filename(request.form['filename'])
         input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
         if not os.path.exists(input_path):
             return jsonify({'error': 'File not found (upload failed?)'}), 400
             
    # 3. Direct Upload
    elif 'file' in request.files:
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No selected file'}), 400
        filename = secure_filename(file.filename)
        input_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(input_path)
        
    else:
        return jsonify({'error': 'No file provided'}), 400

    base_name = os.path.splitext(filename)[0]
    
    # v2.20 Soundfont Selector Logic
    sf_choice = request.form.get('soundfont', 'default')
    
    # Soundfont Map
    SF_MAP = {
        'default': 'GeneralUser-GS.sf2',
        'grand': 'Grandiose.sf2', 
        'harpsichord': 'Harpsiose.sf2',
    }
    
    # Fallback/Safe Resolution
    soundfont = app.config['SOUNDFONT_PATH'] # Default
    
    if sf_choice == 'JSNTH':
        soundfont = 'JSNTH' # Special flag passed to scripts
    elif sf_choice in SF_MAP:
        sf_rel_path = SF_MAP[sf_choice]
        # FIX: Files are in BASE_DIR, not 'soundfonts' subdir
        soundfont = os.path.join(BASE_DIR, os.path.basename(sf_rel_path))
    elif sf_choice != 'default' and sf_choice.endswith('.sf2'):
        # Allow passing full filename if in scanned list (from UI)
        # Security: Allow only if basename exists in directory
        check_path = os.path.join(BASE_DIR, os.path.basename(sf_choice))
        if os.path.exists(check_path):
            soundfont = check_path

    extra_args = []

    if tool_type == 'p2mix':
        script = 'p2mix1.py'
        out_name = f"{base_name}_p2mix.wav"
        # Pass soundfont as positional argument via stream_process
        extra_args = []
        
    elif tool_type == 'cmcmf':
        # Replaced cmcmf.py with cmcmt.py (Clean Rebuild v4.54)
        script = 'cmcmt.py'
        # The input_path (instrument_id) is passed as the first arg by stream_process
        out_name = f"{base_name}_cmcmt.wav"
        
        # Args: [inst_id(dummy), soundfont_arg, --soundfont, --output, --prompt]
        soundfont = app.config['SOUNDFONT_PATH']
        extra_args = ['--soundfont', soundfont]
        
        prompt = request.form.get('prompt', 'A grand encore')
        extra_args.extend(['--prompt', prompt])

    elif tool_type == 'fugue':
        # Replaced fugue.py with tugue.py (Clean Rebuild v4.54)
        script = 'tugue.py'
        out_name = f"{base_name}_tugue.wav"
        
        soundfont = app.config['SOUNDFONT_PATH']
        extra_args = ['--soundfont', soundfont]
        
        prompt = request.form.get('prompt', 'A strict 3-part fugue')
        extra_args.extend(['--prompt', prompt])
        
        
        # 'fav' was undefined causing 500s. Assuming it comes from form data.
        fav = request.form.get('favorite')
        if fav:
            extra_args.extend(['--favorite', fav])

    elif tool_type == 'xymix':
        script = 'xymix.py'
        out_name = f"{base_name}_xymix.wav"
        
        # Force default SoundFont (ignore user selection)
        soundfont = app.config['SOUNDFONT_PATH']
        
        preset = request.form.get('preset')
        if preset:
            extra_args.extend(['--preset', preset])

    elif tool_type == '15010':
        script = '15010.py'
        out_name = f"{base_name}_15010.wav"
        
        # 15010 uses default soundfont usually (GeneralUser)
        # But we still pass whatever resolved soundfont we have
        extra_args = []
        
        fav = request.form.get('fav')
        if fav:
            extra_args.extend(['--favorite', fav])

    elif tool_type == 'xmiox':
        script = 'xmiox.py'
        out_name = f"{base_name}_xmiox.wav"
            
    elif tool_type == 'fina1':
        script = 'fina1.py'
        out_name = f"{base_name}_fina1.wav"
        lufs = request.form.get('lufs')
        style = request.form.get('style', 'OTHER') # Default to OTHER
        
        if lufs:
            extra_args.extend(['--lufs', str(lufs)])
        if style:
            extra_args.extend(['--style', str(style)])
            
    elif tool_type == 'fimai':
        script = 'fimai.py'
        out_name = f"{base_name}_fimai.wav"
        lufs = request.form.get('finalLufs') # Frontend sends finalLufs
        
        extra_args = []
        if lufs:
            extra_args.extend(['--lufs', str(lufs)])
            
    elif tool_type == 'p10no':
        script = 'p10np.py'
        out_name = f"{base_name}_gen.wav"
        
        # P10NP signature: p10np.py [dummy] soundfont --output OUT
        extra_args = ['--soundfont', soundfont] 
        
        # Main.py stream_process appends these to: [python, script, input, output, *extra]
        # p10np expects: dummy_input(ignored), soundfont, --output ...
        # stream_process passes input_path as 2nd arg to subprocess.
        # So: python p10np.py input_path soundfont --output output_path
        
        # We need prompts?
        prompt = request.form.get('prompt', 'Beautiful piano improvisation')
        extra_args.append('--prompt')
        extra_args.append(prompt)

    elif tool_type == 'p20co':
        script = 'p20co.py'
        out_name = f"{base_name}_gen.wav"
        
        # Re-resolve soundfont path just to be safe or reuse variable?
        # Variable 'soundfont' is already resolved in main.py lines 233-238
        
        extra_args = ['--soundfont', soundfont]
        prompt = request.form.get('prompt', 'Beautiful composition')
        extra_args.append('--prompt')
        extra_args.append(prompt)
        
    elif tool_type == 'cmcmf':
        script = 'cmcmf.py'
        out_name = f"{base_name}_final.wav"
        
        # Args: [dummy, soundfont_positional, --soundfont, --output, --instrument, --prompt]
        # cmcmf.py expects: dummy, soundfont_arg, --soundfont, --output, --instrument, --prompt
        
        # Resolve soundfont logic same as others
        # cmcmf.py ignores it mostly but needs a valid path to find GeneralUser
        soundfont = app.config['SOUNDFONT_PATH'] 
        
        extra_args = ['--soundfont', soundfont]
        
        inst_id = request.form.get('instrument', '0')
        extra_args.extend(['--instrument', str(inst_id)])
        
        prompt = request.form.get('prompt', 'A classical masterpiece')
        prompt = request.form.get('prompt', 'A classical masterpiece')
        extra_args.extend(['--prompt', prompt])

    elif tool_type == 'fugue':
        script = 'fugue.py'
        out_name = f"{base_name}_fugue.wav"
        
        # Args: [dummy, soundfont_arg, --soundfont, --output, --prompt]
        soundfont = app.config['SOUNDFONT_PATH']
        extra_args = ['--soundfont', soundfont]
        
        prompt = request.form.get('prompt', 'A strict 3-part fugue')
        extra_args.extend(['--prompt', prompt])

    elif tool_type == 'snata':
        # Replaced snata.py with sonat.py (Clean Rebuild v4.52)
        script = 'sonat.py'
        out_name = f"{base_name}_sonat.wav"
        
        # Args: [dummy, soundfont_arg, --soundfont, --output, --prompt]
        soundfont = app.config['SOUNDFONT_PATH']
        extra_args = ['--soundfont', soundfont]
        
        prompt = request.form.get('prompt', 'A dynamic Piano Sonata')
        extra_args.extend(['--prompt', prompt])

    else:
        return jsonify({'error': 'Invalid tool type'}), 400

    output_path = os.path.join(app.config['WAV_F_FOLDER'], out_name)

    return Response(
        stream_process(script, input_path, output_path, soundfont, extra_args), 
        mimetype='text/event-stream',
        headers={
            'X-Accel-Buffering': 'no',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive'
        }
    )



@app.route('/download/<path:filename>')
def download_file(filename):
    print(f"DEBUG: Download requested for '{filename}'", flush=True)
    
    try:
        # 1. Normalize
        safe_filename = secure_filename(os.path.basename(filename))
        directory = app.config['WAV_F_FOLDER']
        target_path = os.path.join(directory, safe_filename)
        
        # 2. Check Existence
        if not os.path.exists(target_path):
             # Fuzzy fallback (check for partial matches if needed, or just fail)
             # Let's keep it simple: strict match preference
             print(f"DEBUG: File not found: {target_path}", flush=True)
             ls_debug = os.listdir(directory)
             return f"File not found: {safe_filename}\nAvailable ({len(ls_debug)}): {ls_debug[:10]}...", 404

        # 3. Permissions Safety (Just in case)
        try:
            os.chmod(target_path, 0o644)
        except Exception as e_perm:
            print(f"WARN: Failed to chmod {target_path}: {e_perm}", flush=True)

        # 4. Stream File (Nuclear Option: Manual Chunking)
        # send_from_directory was choking on large files in RAM.
        # We manually stream it to bypass any Gunicorn/Flask buffering.
        def generate():
            with open(target_path, 'rb') as f:
                while True:
                    chunk = f.read(8192) # 8KB chunks
                    if not chunk: break
                    yield chunk

        print(f"DEBUG: Streaming file {target_path}", flush=True)
        return Response(stream_with_context(generate()), 
                        mimetype="audio/wav", # Force WAV for now, or use mimetypes.guess_type if needed
                        headers={"Content-Disposition": f"attachment; filename={safe_filename}"})

    except Exception as e:
        print(f"CRITICAL: Download Handler Failed: {e}", flush=True)
        return Response(f"System Error (Download):\n{e}\n{traceback.format_exc()}", mimetype='text/plain', status=500)
        
@app.route('/download/listall')
def download_listall():
    """List all files in WAV_F_FOLDER with download links."""
    root_dir = app.config['WAV_F_FOLDER']
    files = []
    try:
        if os.path.exists(root_dir):
            for f in os.listdir(root_dir):
                if not f.startswith('.'): # Skip hidden
                    files.append(f)
            files.sort()
    except Exception as e:
        return f"Error listing files: {e}", 500

    # Simple HTML
    html = "<h1>File Storage listing for /tmp/wavF (Ephemeral)</h1><ul>"
    for f in files:
        html += f'<li><a href="/download/{f}">{f}</a></li>'
    html += "</ul>"
    return html

def cleanup_old_files(days=7):
    """Deletes files in WAV_F_FOLDER older than specified days."""
    root_dir = app.config['WAV_F_FOLDER']
    now = time.time()
    cutoff = now - (days * 86400)
    deleted_count = 0
    
    try:
        if os.path.exists(root_dir):
            for f in os.listdir(root_dir):
                fpath = os.path.join(root_dir, f)
                if os.path.isfile(fpath):
                    try:
                        if os.path.getmtime(fpath) < cutoff:
                            os.remove(fpath)
                            deleted_count += 1
                    except: pass
    except: pass
    return deleted_count

@app.route('/api/debug_files')
@app.route('/debug/ls')
def debug_ls():
    """List all files in WAV_F_FOLDER with permissions (ls -l style). Auto-cleans old files."""
    # Run Cleanup First
    cleaned = cleanup_old_files(7)
    
    root_dir = app.config['WAV_F_FOLDER']
    lines = []
    lines.append(f"root: {root_dir} | Auto-Cleaned: {cleaned} files older than 7 days")
    try:
        if os.path.exists(root_dir):
            for root, dirs, files in os.walk(root_dir):
                for name in files:
                    filepath = os.path.join(root, name)
                    try:
                        st = os.stat(filepath)
                        perm = oct(st.st_mode)[-3:]
                        uid = st.st_uid
                        gid = st.st_gid
                        size = st.st_size
                        lines.append(f"{perm} {uid}:{gid} {size} {filepath}")
                    except:
                        lines.append(f"??? ? ? {filepath}")
    except Exception as e:
        return f"Error listing files: {e}", 500

    return "<pre>" + "\\n".join(lines) + "</pre>"

@app.route('/debug/inspect/<path:filename>')
def debug_inspect_file(filename):
    """
    Diagnostic tool to inspect a specific file in WAV_F_FOLDER.
    Returns JSON stats and attempts to read 64 bytes.
    """
    directory = app.config['WAV_F_FOLDER']
    target_path = os.path.join(directory, secure_filename(filename))
    
    if not os.path.exists(target_path):
        return jsonify({"error": "File not found", "path": target_path}), 404
        
    stats = {}
    read_test = "Pending"
    try:
        st = os.stat(target_path)
        stats = {
            "mode": oct(st.st_mode),
            "size": st.st_size,
            "uid": st.st_uid,
            "gid": st.st_gid,
            "path": target_path
        }
        
        # Test Read
        with open(target_path, 'rb') as f:
            head = f.read(64)
            read_test = f"Success. Head (hex): {head.hex()}"
            
    except Exception as e:
        read_test = f"FAILED: {e}\n{traceback.format_exc()}"
        
    return jsonify({
        "stats": stats,
        "read_test": read_test
    })

@app.route('/api/xml0x/parse_midi', methods=['GET'])
def parse_midi_api():
    """
    Parses a server-side MIDI file and returns a simplified JSON event list.
    Args:
        path: Absolute path to the midi file (or relative to allowed folders).
    Returns:
        JSON: { "events": [ { "n": note, "v": vel, "t": time, "type": "on" }, ... ], "duration": X }
    """
    path = request.args.get('path')
    if not path:
        return jsonify({"error": "No path provided"}), 400

    # Security/Validity Check (Simple)
    # Ensure it's inside allowed dirs if possible, or just exists.
    # For now, trust the path if it exists (since we generate them).
    if not os.path.exists(path):
        return jsonify({"error": "File not found"}), 404
        
    try:
        mid = mido.MidiFile(path)
        events = []
        current_time = 0.0
        
        # Iterate through messages. 
        # mido `for msg in mid` yields messages with `delta` time converted to seconds (msg.time).
        
        for msg in mid:
            current_time += msg.time
            
            if msg.type == 'note_on':
                if msg.velocity > 0:
                    events.append({
                        "t": round(current_time, 3),
                        "type": "on",
                        "n": msg.note,
                        "v": msg.velocity
                    })
                else:
                    # note_on with vel 0 is note_off
                    events.append({
                        "t": round(current_time, 3),
                        "type": "off",
                        "n": msg.note
                    })
            elif msg.type == 'note_off':
                events.append({
                    "t": round(current_time, 3),
                    "type": "off",
                    "n": msg.note
                })
                
        return jsonify({
            "duration": mid.length,
            "events": events
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Cloud Run populates PORT env var. Default to 8080.
    port = int(os.environ.get('PORT', 8080))
    app.run(debug=True, host='0.0.0.0', port=port)

