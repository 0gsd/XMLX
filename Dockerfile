# Use PyTorch with CUDA support for GPU acceleration
FROM pytorch/pytorch:2.1.0-cuda11.8-cudnn8-runtime

# Set the working directory in the container
WORKDIR /app

# Prevent interactive prompts (tzdata)
# Prevent interactive prompts (tzdata)
ENV DEBIAN_FRONTEND=noninteractive
ENV MKL_THREADING_LAYER=GNU

# Install system dependencies (ffmpeg, fluidsynth required)
RUN apt-get update && apt-get install -y \
    ffmpeg \
    fluidsynth \
    git \
    build-essential \
    libsndfile1 \
    wget \
    xz-utils \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies from requirements file
RUN pip install --no-cache-dir -r requirements.txt

# Download models logic if needed...

# Set the working directory
WORKDIR /app


# Copy the entire p2mix folder into /app
COPY . /app

# Copy the models (now strictly local in ./inf) to /inf
COPY inf /inf

# Set up Piano Transcription Data from local source (No more wget)
# Expects: ./inf/piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth
RUN mkdir -p /root/piano_transcription_inference_data && \
    cp /inf/piano_transcription_inference_data/note_F1=0.9677_pedal_F1=0.9186.pth /root/piano_transcription_inference_data/

# --- SOUNDFONTS (v2.20) ---
RUN mkdir -p /app/soundfonts

# 1. Salamander Grand V3 (Tar.xz -> SF2)
# URL: https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPianoV3+20161209_48khz24bit.tar.xz
# Using 'find' to locate the sf2 file regardless of internal folder structure
RUN wget -O /tmp/salamander.tar.xz "https://freepats.zenvoid.org/Piano/SalamanderGrandPiano/SalamanderGrandPianoV3+20161209_48khz24bit.tar.xz" && \
    mkdir -p /tmp/salamander_extract && \
    tar -xJf /tmp/salamander.tar.xz -C /tmp/salamander_extract && \
    find /tmp/salamander_extract -name "*.sf2" -exec mv {} /app/soundfonts/SalamanderGrandPianoV3.sf2 \; && \
    rm -rf /tmp/salamander.tar.xz /tmp/salamander_extract

# 2. Upright Piano (Placeholder)
# Unstable download links. Using GeneralUser-GS as placeholder to ensure build success.
RUN cp /app/GeneralUser-GS.sf2 /app/soundfonts/BinauralUpright.sf2

# 3. Honky Tonk / Bright (Placeholders)
RUN cp /app/GeneralUser-GS.sf2 /app/soundfonts/YamahaHybrid.sf2
RUN cp /app/GeneralUser-GS.sf2 /app/soundfonts/HonkyTonk.sf2

# v2.30 Additions:
# 4. Grandiose & Harpsiose (Local Files)
COPY Grandiose.sf2 /app/soundfonts/Grandiose.sf2
COPY Harpsiose.sf2 /app/soundfonts/Harpsiose.sf2

# Run the unified app
# Run with Gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "8", "--timeout", "0", "main:app"]
