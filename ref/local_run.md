# Running FINA1 Locally (Guide)

You asked if you can run `fina1.py` locally to avoid deploying for every test.
**YES, YOU CAN!**

Here is how to set it up.

## 1. Prerequisites
You need the python dependencies installed on your Mac.

```bash
# Install system libs (if missing)
brew install ffmpeg

# Install Python libs
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu  # or just pip install torch if on Mac ARM64
pip install demucs roex-python pydub requests
```

## 2. Running the Script
The `fina1.py` script accepts command-line arguments.

**Basic Usage:**
```bash
cd tools/musicgen/p2mix
python3 fina1.py /path/to/your/input.wav /path/to/output/folder --style ELECTRONIC --lufs -14
```

**Arguments:**
*   `input_wav`: Path to source file (Absolute path is best).
*   `output_dir`: Where to save results.
*   `--style`: `ROCK_INDIE`, `POP`, `ACOUSTIC`, `HIPHOP_GRIME`, `ELECTRONIC`, `REGGAE_DUB`, `ORCHESTRAL`, `METAL`, `OTHER` (Default).
*   `--lufs`: Target Loudness (e.g. `-14`).

## 3. Notes
*   **API Key**: The script currently has the RoEx API key hardcoded (PROD key), so it should "just work" without env vars.
*   **Performance**: `demucs` will use your CPU/GPU. On Apple Silicon (M1/M2/M3), it's decently fast (MPS acceleration is automatic in recent torch versions).
*   **Paths**: Ensure your output folder exists or the script might complain (though it usually creates temp folders).

## Sample Command (Try this!)
```bash
python3 tools/musicgen/p2mix/fina1.py \
  /Users/0gs/Documents/METMcloud/METMroot/tools/musicgen/p2mix/ref/test.wav \
  /tmp/fina1_local_test \
  --style POP
```
