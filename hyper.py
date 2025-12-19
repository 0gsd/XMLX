import random
import os
from midiutil import MIDIFile

def generate_the_future():
    # --- 1. THE GENRE GENERATOR (36 VARIATIONS) ---
    prefixes = ["Post-", "Hyper-", "Neo-", "Meta-", "Cyber-", "Glitch-"]
    cores = ["Abundance", "Dopamine", "Data", "Neural", "Silicon", "Void"]
    suffixes = ["Gaze", "Core", "Pop", "Trash", "Sludge", "Flux"]
    
    genre_name = f"{random.choice(prefixes)}{random.choice(cores)}{random.choice(suffixes)}"
    print(f"INITIALIZING GENERATION SEQUENCE FOR GENRE: '{genre_name}'")
    print("...sounds can and will insole theirself upon and with you...")

    # --- 2. SETUP (THE "STUFF") ---
    bpm = random.randint(145, 175) # High energy for the future
    mid = MIDIFile(4) # 4 Tracks: Kick, Snare, Bass, Melody
    
    # Calculate duration to fit 24-54s window, multiple of 4 bars
    # 1 bar at 160bpm is ~1.5s. 
    # 16 bars ~ 24s. 32 bars ~ 48s.
    num_bars = random.choice([16, 20, 24, 28, 32])
    duration_sec = (num_bars * 4) * (60 / bpm)
    
    print(f"BPM: {bpm} | BARS: {num_bars} | DURATION: {duration_sec:.2f}s")
    
    # Track Names
    tracks = {
        "kick": 0,
        "snare": 1,
        "bass": 2,
        "melody": 3
    }
    
    for name, idx in tracks.items():
        mid.addTrackName(idx, 0, f"Future_{name}_{genre_name}")
        mid.addTempo(idx, 0, bpm)

    # --- 3. HARMONIC ARCHITECTURE (EMOTIONAL CHORDS) ---
    # We use a Lydian/Major vibe: I - V - vi - IV (Classic but effective)
    # Root: C (60), G (67), A (69), F (65)
    # Scale (C Major / A Minor): C D E F G A B
    scale = [60, 62, 64, 65, 67, 69, 71, 72, 74, 76, 77, 79] 
    chord_progression = [0, 7, 9, 5] # Offsets from C (C, G, A, F)
    
    # --- 4. GENERATION LOOP ---
    for bar in range(num_bars):
        # Determine current chord root
        root_offset = chord_progression[bar % 4]
        root_note = 60 + root_offset
        
        # --- TRACK 0 & 1: DRUMS (The "Kitchen Sink" Breakbeat) ---
        # Kick: Heavy on 1, syncopated elsewhere
        mid.addNote(tracks["kick"], 9, 36, bar * 4, 0.5, 120) # Downbeat
        if random.random() > 0.3: mid.addNote(tracks["kick"], 9, 36, bar * 4 + 2.5, 0.5, 110) # Syncopation
        
        # Snare: Driving backbeat on 2 and 4
        mid.addNote(tracks["snare"], 9, 38, bar * 4 + 1, 0.5, 127)
        mid.addNote(tracks["snare"], 9, 38, bar * 4 + 3, 0.5, 127)
        
        # Glitch Fills (The "Jane Remove" Stutter)
        # Randomly at the end of bars, burst 32nd notes
        if random.random() > 0.7:
            for i in range(8):
                mid.addNote(tracks["snare"], 9, 38, bar * 4 + 3.5 + (i * 0.0625), 0.06, 80 + (i*5))

        # --- TRACK 2: BASS (The Foundation) ---
        # Long, deep notes. Maybe a distorted saw.
        # "Underscores" style: occasionally drop out for silence
        if random.random() > 0.1: 
            mid.addNote(tracks["bass"], 0, root_note - 12, bar * 4, 4, 110)
            # Add a 5th for thickness
            mid.addNote(tracks["bass"], 0, root_note - 5, bar * 4, 4, 90)

        # --- TRACK 3: MELODY (The "Maximalist Joy") ---
        # High density. Arpeggios, flourishes, counter-harmonies.
        current_time = bar * 4
        while current_time < (bar + 1) * 4:
            # Pick a duration: favoring fast 16th notes (0.25) or 8th (0.5)
            # Glitch probability: 32nd note bursts
            is_glitch = random.random() > 0.85
            duration = 0.125 if is_glitch else random.choice([0.25, 0.25, 0.5, 1.0])
            
            # Note selection: Stay in scale, prioritize chord tones but allow "flourishes"
            # Chord tones: Root, 3rd, 5th relative to current root
            chord_tones = [root_note, root_note+4, root_note+7, root_note+12, root_note+16]
            
            if random.random() > 0.4:
                note = random.choice(chord_tones) # Safe note
            else:
                note = random.choice(scale) # Scale run
                if note < root_note: note += 12 # Keep it high
            
            # Add the note
            # Velocity varies wildly for "Human Optimization"
            velocity = random.randint(70, 127)
            mid.addNote(tracks["melody"], 1, note + 12, current_time, duration, velocity)
            
            # Counter-Harmony (The "All at once" vibe)
            if random.random() > 0.6:
                harmony_note = note + random.choice([3, 4, 7]) # create 3rd/5th harmony
                mid.addNote(tracks["melody"], 1, harmony_note + 12, current_time, duration, velocity - 20)

            current_time += duration

    # --- 5. EXPORT ---
    output_dir = "midiO"
    os.makedirs(output_dir, exist_ok=True)
    filename = os.path.join(output_dir, f"future_hyper_glitch_{genre_name}.mid")
    
    with open(filename, "wb") as output_file:
        mid.writeFile(output_file)
    
    print(f"GENERATION COMPLETE. FILE SAVED AS: {filename}")
    print("STATUS: OPTIMIZED JOY DETECTED.")

if __name__ == "__main__":
    generate_the_future()
