import argparse
import copy
from music21 import converter, stream, note, chord, tempo, key, interval, pitch

def convolve_midi(input_mid, output_mid):
    print(f"   [P20CO] Convolving {input_mid}...", flush=True)
    
    # 1. Load Original
    s_original = converter.parse(input_mid)
    
    # 2. Key Analysis (for harmonious motifs)
    analyzed_key = s_original.analyze('key')
    print(f"   [P20CO] Detected Key: {analyzed_key.name}", flush=True)
    
    # 3. Create Slowed Version (Deep Copy & Stretch)
    # We want to stretch durations and offsets by 2x
    s_slow = stream.Score()
    
    # Flatten original to handle parts/voices easily for this transformation
    s_flat = s_original.flatten()
    
    # iterate and stretch
    # We'll build a new part for the slowed version
    part_slow = stream.Part()
    part_slow.id = 'Slowed_Original'
    
    # Copy Elements but 2x timing
    for el in s_flat.notesAndRests:
        new_el = copy.deepcopy(el)
        new_el.offset = el.offset * 2.0
        new_el.duration.quarterLength = el.duration.quarterLength * 2.0
        part_slow.insert(new_el.offset, new_el)
        
    s_slow.append(part_slow)
    
    # 4. Generate Motifs
    # Motifs should be harmonious (in key) and rhythmic.
    # Approach: Generate simple arpeggios or scale runs periodically.
    part_motifs = stream.Part()
    part_motifs.id = 'Motifs'
    
    # Motif Length in beat
    total_duration = part_slow.highestTime
    
    # Create a scale object for the key
    sc = analyzed_key.getScale()
    
    current_offset = 0.0
    
    import random
    
    while current_offset < total_duration:
        # 30% chance to generate a motif at this beat, otherwise rest
        if random.random() < 0.3:
            # Motif Type: Arpeggio or Scale Run
            motif_type = random.choice(['arp', 'run'])
            length = random.choice([1.0, 2.0, 4.0]) # Quarter length of motif
            
            # Start Note: Random note from tonic chord
            tonic_chord = analyzed_key.getChord(analyzed_key.tonic)
            start_pitch = random.choice(tonic_chord.pitches)
            # Randomize octave (C3-C5)
            start_pitch.octave = random.randint(3, 5)
            
            current_pitch = start_pitch
            
            # Generate notes for motif
            # 16th notes (0.25 qL) for shimmer
            num_notes = int(length / 0.25)
            
            for i in range(num_notes):
                n = note.Note(current_pitch)
                n.quarterLength = 0.25
                # velocity low for background texture
                n.volume.velocity = 60 
                part_motifs.insert(current_offset + (i * 0.25), n)
                
                # Next pitch
                if motif_type == 'arp':
                    # Thirds
                    current_pitch = sc.nextPitch(current_pitch, stepSize=2)
                else:
                    # Steps
                    current_pitch = sc.nextPitch(current_pitch, stepSize=1)
                    
            current_offset += length
        else:
            # Skip forward
            current_offset += 2.0
            
    s_slow.append(part_motifs)
    
    # 5. Extend & Evolve
    print(f"   [P20CO] Extending and Evolving...", flush=True)
    # Pass s_original directly to extend_and_evolve (no pre-stretch)
    s_final = extend_and_evolve(s_original, analyzed_key)

    # 6. Write Output
    s_final.write('midi', fp=output_mid)
    print(f"   [P20CO] Saved Extended-Evolved MIDI to {output_mid}", flush=True)

def force_diatonic(p, sc):
    """
    Snap a pitch to the nearest note in the given scale.
    """
    if sc.contains(p):
        return p
    
    # Simple nearest neighbor search
    # We compare against scale pitches in the same octave
    candidates = [pt for pt in sc.getPitches(p.nameWithOctave, p.nameWithOctave) if pt]
    # If getPitches is empty (range issue), just get generic scale pitches
    if not candidates:
        # Construct scale in this octave
        base_pitches = sc.getPitches('C'+str(p.octave), 'B'+str(p.octave))
        candidates = base_pitches
        
    if not candidates: return p # Safety fallback

    # Find closest by midi value
    return min(candidates, key=lambda x: abs(x.midi - p.midi))


def extend_and_evolve(base_stream, key_obj):
    """
    Takes the convolved stream and builds a 2x length masterpiece.
    Layer 1: Half Speed (Foundation)
    Layer 2: 2x Normal Speed (Evolving Motif) -> Auto-Tuned!
    Layer 3: Counterpoints (Sparkles)
    """
    final_score = stream.Score()
    
    # --- Layer 1: Foundation (Half Speed) ---
    # We take the entire 30s (approx) base and stretch to 60s
    part_l1 = stream.Part()
    part_l1.id = 'L1_Foundation'
    
    base_flat = base_stream.flatten()
    
    for el in base_flat.notesAndRests:
        new_el = copy.deepcopy(el)
        new_el.offset = el.offset * 2.0
        new_el.duration.quarterLength = el.duration.quarterLength * 2.0
        # Lower velocity for foundation
        if isinstance(new_el, note.Note):
            new_el.volume.velocity = int(new_el.volume.velocity * 0.8)
        elif isinstance(new_el, chord.Chord):
            for p in new_el.pitches:
                new_el.volume.velocity = int(new_el.volume.velocity * 0.8)
                
        part_l1.insert(new_el.offset, new_el)
        
    final_score.append(part_l1)
    
    # --- Layer 2: Evolving Motif (2x Normal Speed) ---
    # We place the base stream twice. The second time, we evolve it.
    part_l2 = stream.Part()
    part_l2.id = 'L2_Evolving'
    
    # Segment A (Original)
    duration_base = base_stream.highestTime
    
    for el in base_flat.notesAndRests:
        new_el = copy.deepcopy(el)
        part_l2.insert(new_el.offset, new_el)
        
    # Segment B (Evolved & Auto-Tuned)
    # Evolve: Shift pitch of 40% of notes by a scale step
    sc = key_obj.getScale()
    import random
    
    for el in base_flat.notesAndRests:
        new_el = copy.deepcopy(el)
        # Shift offset to start after Segment A
        new_el.offset += duration_base
        
        if isinstance(new_el, note.Note) or isinstance(new_el, chord.Chord):
            if random.random() < 0.4:
                # Evolve
                try:
                    if isinstance(new_el, note.Note):
                        # 1. Snap original to key (Auto-Tune Input)
                        safe_pitch = force_diatonic(new_el.pitch, sc)
                        
                        # 2. Shift up or down 1 scale step (Diatonic Shift)
                        step = random.choice([-1, 1])
                        new_pitch = sc.nextPitch(safe_pitch, stepSize=step)
                        
                        # 3. Assign
                        new_el.pitch = new_pitch
                        
                    elif isinstance(new_el, chord.Chord):
                        # Invert chord or move root
                        new_el = new_el.closedPosition()
                except:
                    pass # Fallback to original
                
        part_l2.insert(new_el.offset, new_el)
        
    final_score.append(part_l2)
    
    # --- Layer 3: Counterpoints (Sparkles) ---
    # Generate high-register harmonies for Layer 2's notes
    part_l3 = stream.Part()
    part_l3.id = 'L3_Counterpoint'
    
    l2_flat = part_l2.flatten()
    
    for el in l2_flat.notes: # notes and chords
        # Only add counterpoint on beats (approx) to avoid clutter
        if el.offset % 1.0 == 0: 
            if random.random() < 0.5:
                continue # Sparse
            
            try:
                # Get reference pitch
                if isinstance(el, note.Note):
                    ref_pitch = el.pitch
                else:
                    ref_pitch = el.pitches[-1] # Top note of chord
                
                # Create a harmony note (3rd or 5th up)
                interval_step = random.choice([2, 4]) # 3rd=2 steps, 5th=4 steps in diatonic
                harm_pitch = sc.nextPitch(ref_pitch, stepSize=interval_step)
                
                # Shift to higher register if needed (keep above C5)
                while harm_pitch.midi < 72: # C5
                    harm_pitch.octave += 1
                    
                n = note.Note(harm_pitch)
                n.quarterLength = 0.5 # Short stabs
                n.volume.velocity = 70
                
                part_l3.insert(el.offset, n)
            except:
                pass
                
    final_score.append(part_l3)
    
    return final_score

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    
    convolve_midi(args.input, args.output)
