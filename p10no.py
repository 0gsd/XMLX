import music21
from music21 import stream, note, chord, tempo, key, instrument, scale, interval, pitch
import random
import numpy as np
import copy
import time
from textblob import TextBlob

class ClassicalComposer:
    def __init__(self, prompt, duration_minutes=3):
        self.prompt = prompt
        self.target_duration = duration_minutes * 60  # seconds
        
        # 1. Analyze Sentiment using NLP (TextBlob)
        try:
            blob = TextBlob(prompt)
            self.sentiment = blob.sentiment
        except Exception as e:
            print(f"NLP Error (using defaults): {e}")
            self.sentiment = type('obj', (object,), {'polarity': 0.0, 'subjectivity': 0.5})
        
        print(f"Initializing Composition: '{self.prompt}'")
        print(f"NLP Analysis -> Polarity: {self.sentiment.polarity:.2f} | Subjectivity: {self.sentiment.subjectivity:.2f}")

        # 2. Determine Musical Parameters
        self.key_signature, self.scale_obj = self._determine_key_and_scale()
        self.bpm = self._determine_tempo()
        self.complexity = self._determine_complexity()
        
        # 3. Generate the core "DNA"
        self.motif = self._text_to_motif()
        self.score = stream.Score()
        
        print(f"Key: {self.key_signature.name} | Scale: {self.scale_obj.name} | Tempo: {self.bpm} BPM | Complexity: {self.complexity:.2f}")

    def _determine_key_and_scale(self):
        """
        Determines the Key Signature and Scale Object.
        Now correctly instantiates specific Mode classes to avoid empty pitch lists.
        """
        tonics = ['C', 'D', 'E', 'F', 'G', 'A', 'B']
        tonic = random.choice(tonics)
        
        # Add accidentals based on complexity/randomness
        if random.random() > 0.7:
            tonic += random.choice(['#', '-'])
            
        # High polarity (> 0.3) -> Major
        if self.sentiment.polarity > 0.3:
            return key.Key(tonic, 'major'), scale.MajorScale(tonic)
            
        # Low polarity (< -0.3) -> Minor or Harmonic Minor
        elif self.sentiment.polarity < -0.3:
            if random.random() > 0.5:
                # Harmonic Minor uses Minor Key Sig but specific Scale intervals
                return key.Key(tonic, 'minor'), scale.HarmonicMinorScale(tonic)
            else:
                return key.Key(tonic, 'minor'), scale.MinorScale(tonic)
        
        # Neutral/Complex -> Exotic Modes
        else:
            mode_type = random.choice(['dorian', 'lydian', 'mixolydian', 'phrygian'])
            
            # Map string to actual music21 Scale Class
            if mode_type == 'dorian':
                return key.Key(tonic, 'dorian'), scale.DorianScale(tonic)
            elif mode_type == 'lydian':
                return key.Key(tonic, 'lydian'), scale.LydianScale(tonic)
            elif mode_type == 'mixolydian':
                return key.Key(tonic, 'mixolydian'), scale.MixolydianScale(tonic)
            elif mode_type == 'phrygian':
                return key.Key(tonic, 'phrygian'), scale.PhrygianScale(tonic)
            else:
                # Fallback to Major
                return key.Key(tonic, 'major'), scale.MajorScale(tonic)

    def _determine_tempo(self):
        base_bpm = 100 + (self.sentiment.polarity * 40)
        variation = random.randint(-15, 15)
        
        fast_words = ['fast', 'run', 'race', 'storm', 'battle', 'quick', 'allegro']
        slow_words = ['slow', 'adagio', 'sleep', 'dream', 'calm', 'wait']
        
        for word in self.prompt.lower().split():
            if word in fast_words: base_bpm += 20
            if word in slow_words: base_bpm -= 20
            
        return int(max(40, min(200, base_bpm + variation)))

    def _determine_complexity(self):
        base = 0.3 + (self.sentiment.subjectivity * 0.3)
        complex_words = ['complex', 'virtuoso', 'hard', 'intricate', 'chaos', 'math', 'fractal']
        for word in self.prompt.lower().split():
            if word in complex_words: base += 0.2
        return min(base + random.uniform(-0.1, 0.2), 1.0)

    def _text_to_motif(self):
        """Generates a musical motif from text characters."""
        motif_notes = []
        
        # Safety Check: Ensure scale generates pitches
        try:
            scale_pitches = self.scale_obj.getPitches('C4', 'C6')
        except:
            scale_pitches = []

        # Fallback if scale object is still behaving mostly abstractly
        if not scale_pitches or len(scale_pitches) == 0:
            print("Warning: Scale generated no pitches. Falling back to Chromatic.")
            scale_pitches = [pitch.Pitch('C4').transpose(i) for i in range(24)]
        
        relevant_chars = [c for c in self.prompt.lower() if c.isalpha()]
        if not relevant_chars: relevant_chars = ['a', 'b', 'c']
        
        seed_chars = relevant_chars[:min(len(relevant_chars), random.randint(4, 8))]
        
        for char in seed_chars:
            # Map char to scale degree
            idx = (ord(char) - 97) % len(scale_pitches)
            p = scale_pitches[idx]
            
            if self.complexity > 0.6:
                dur_type = random.choice(['quarter', 'eighth', '16th'])
            else:
                dur_type = random.choice(['half', 'quarter', 'eighth'])
                
            n = note.Note(p)
            n.duration.type = dur_type
            motif_notes.append(n)
            
        return motif_notes

    def _harmonize_melody(self, melody_measure, style='arpeggio'):
        try:
            target_note = melody_measure.notes[0]
        except IndexError:
            return stream.Measure()

        root = target_note.pitch
        # Use simple interval transposition if scale logic fails for specific degrees
        try:
            third = self.scale_obj.nextPitch(root, stepSize=2)
            fifth = self.scale_obj.nextPitch(root, stepSize=4)
            chord_pitches = [root, third, fifth]
        except:
            # Fallback to major/minor triads if scale.next() fails
            chord_pitches = [root, root.transpose(4), root.transpose(7)]

        bass_pitches = [p.transpose(-24) for p in chord_pitches]
        
        lh_measure = stream.Measure()
        
        if style == 'block':
            c = chord.Chord(bass_pitches)
            c.duration.type = 'whole' if melody_measure.duration.quarterLength >= 4 else 'half'
            lh_measure.append(c)
            
        elif style == 'alberti':
            dur = '16th' if self.complexity > 0.7 else 'eighth'
            pattern = [bass_pitches[0], bass_pitches[2], bass_pitches[1], bass_pitches[2]]
            for _ in range(2): 
                for p in pattern:
                    n = note.Note(p)
                    n.duration.type = dur
                    lh_measure.append(n)
                    
        elif style == 'arpeggio':
            full_arp = bass_pitches + [bass_pitches[1].transpose(12)] 
            dur = 'eighth'
            for p in full_arp:
                n = note.Note(p)
                n.duration.type = dur
                lh_measure.append(n)
                
        return lh_measure

    def _develop_motif(self, original_motif, method='transposition'):
        new_motif = []
        for n_proto in original_motif:
            n = copy.deepcopy(n_proto)
            
            if method == 'inversion':
                start_pitch = original_motif[0].pitch
                interval_val = interval.notesToInterval(original_motif[0], n_proto)
                n.pitch = start_pitch.transpose(interval_val.semitones * -1)
                
            elif method == 'transposition':
                trans_int = random.choice([7, -5, 2, -2])
                n.pitch = n.pitch.transpose(trans_int)
                
            new_motif.append(n)
            
        return new_motif

    def compose(self):
        piano_rh = stream.Part()
        piano_lh = stream.Part()
        piano_rh.insert(0, instrument.Piano())
        piano_lh.insert(0, instrument.Piano())
        
        piano_rh.insert(0, tempo.MetronomeMark(number=self.bpm))
        piano_rh.insert(0, self.key_signature)
        piano_lh.insert(0, self.key_signature)

        # Exposition
        for _ in range(2):
            for n_proto in self.motif:
                n = copy.deepcopy(n_proto)
                piano_rh.append(n)

        # Development Loop
        total_beats = self.target_duration * (self.bpm / 60)
        generated_beats = 0
        
        theme_b = self._develop_motif(self.motif, 'transposition')
        theme_c = self._develop_motif(self.motif, 'inversion')
        
        print(f"Generating measures for {self.target_duration}s duration...")
        
        while generated_beats < total_beats:
            m_rh = stream.Measure()
            
            if generated_beats < total_beats * 0.3:
                material = self.motif
            elif generated_beats < total_beats * 0.7:
                material = random.choice([theme_b, theme_c])
            else:
                material = self.motif

            current_beat = 0
            for n_proto in material:
                if current_beat >= 4.0: break
                n = copy.deepcopy(n_proto)
                m_rh.append(n)
                current_beat += n.duration.quarterLength

            style = 'alberti' if self.complexity < 0.5 else 'arpeggio'
            if random.random() > 0.7: style = 'block'
            m_lh = self._harmonize_melody(m_rh, style=style)

            piano_rh.append(m_rh)
            piano_lh.append(m_lh)
            generated_beats += 4

        # Ending
        try:
            final_chord_pitches = [self.scale_obj.tonic, self.scale_obj.nextPitch(self.scale_obj.tonic, 2), self.scale_obj.nextPitch(self.scale_obj.tonic, 4)]
        except:
             # Fallback if scale object fails
             final_chord_pitches = [pitch.Pitch('C4'), pitch.Pitch('E4'), pitch.Pitch('G4')]

        c_rh = chord.Chord(final_chord_pitches)
        c_rh.duration.type = 'whole'
        c_rh.volume.velocity = 110
        
        c_lh = chord.Chord([p.transpose(-12) for p in final_chord_pitches])
        c_lh.duration.type = 'whole'
        
        piano_rh.append(c_rh)
        piano_lh.append(c_lh)

        self.score.insert(0, piano_rh)
        self.score.insert(0, piano_lh)
        
        return self.score

    def save_midi(self, filename=None):
        if not filename:
            # Unique filename with timestamp
            filename = f"composition_{int(time.time())}.mid"
        self.score.write('midi', fp=filename)
        print(f"Saved: {filename}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="P10NO Generative Piano")
    parser.add_argument("--prompt", type=str, default="A stormy and complex battle between darkness and light, ending in triumphant victory", help="Text prompt for composition")
    parser.add_argument("--duration", type=float, default=3.0, help="Duration in minutes")
    parser.add_argument("--output", type=str, default=None, help="Output MIDI filename")
    
    args = parser.parse_args()
    
    composer = ClassicalComposer(args.prompt, duration_minutes=args.duration)
    composer.compose()
    composer.save_midi(filename=args.output)