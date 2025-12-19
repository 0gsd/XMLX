"""
pysynth.py - Synthesizer Library (Vendored)

A lightweight Python synthesizer used for rendering MIDI to audio when FluidSynth is unavailable
or lightweight synthesis is preferred. Modified/customized for XMLX usage.
"""
import numpy as np
import mido
import scipy.signal
# scipy.io.wavfile is needed but we might use soundfile or built-in wave if scipy is strictly pinned or older.
# p2mix uses soundfile or scipy.io.wavfile.
import scipy.io.wavfile
import os

SAMPLE_RATE = 44100

class PySynth:
    def __init__(self, sample_rate=44100):
        self.sr = sample_rate

    def _time_array(self, duration):
        return np.linspace(0, duration, int(self.sr * duration), endpoint=False)

    def _adsr(self, length, attack, decay, sustain_level, release, note_dur):
        # Current implementation: Simple linear/exponential ramps matching JS logic roughly
        # JS logic:
        # Piano: Linear Attack 0.01, Exp Decay 2.0
        # Strings: Linear Attack 0.5
        # Guitar: Linear Attack 0.01, Exp Decay 1.0
        
        # We simplify for "Note Duration" based rendering.
        # If note_dur is provided, we assume release happens after note_dur.
        # Total length = length samples.
        
        # Create an envelope array of 'length' size
        env = np.ones(length)
        
        t = np.arange(length) / self.sr
        
        # Attack
        attack_samples = int(attack * self.sr)
        if attack_samples > length: attack_samples = length
        env[:attack_samples] = np.linspace(0, 1, attack_samples)
        
        # Decay (after attack, up to release or end)
        decay_start = attack_samples
        # ... this is getting complex for a simple script. 
        # Let's stick to the specific "Preset" logic defined in JS.
        
        return t, env

    # --- Waveforms ---
    
    def _sine(self, freq, t):
        return np.sin(2 * np.pi * freq * t)

    def _saw(self, freq, t):
        return scipy.signal.sawtooth(2 * np.pi * freq * t)

    def _square(self, freq, t):
        return scipy.signal.square(2 * np.pi * freq * t)

    def _triangle(self, freq, t):
        return scipy.signal.sawtooth(2 * np.pi * freq * t, width=0.5)

    def _noise(self, length):
        return np.random.uniform(-1, 1, length)

    # --- Instruments ---

    def render_drum(self, instrument_id, velocity=1.0):
        # TR-606 Logic
        
        if instrument_id == 'kick':
            # 150 -> 40 Hz sweep, 0.5s decay
            dur = 0.5
            t = self._time_array(dur)
            # Frequency Sweep
            # f(t) = f_start * (f_end/f_start)^(t/dur)
            freq = 150 * (40/150)**(t/0.1) # Fast drop in 0.1s
            freq[int(0.1*self.sr):] = 40 # Clamp
            
            sig = np.sin(2 * np.pi * np.cumsum(freq) / self.sr)
            # Gain Envelope
            env = np.exp(-t * 10) 
            return sig * env * velocity

        elif instrument_id == 'snare':
            # Tone: 250hz Triangle, 0.2s duration
            dur = 0.3 # Tone 0.2, Noise 0.3
            t = self._time_array(dur)
            
            # Tone Component
            tone_t = t[:int(0.2*self.sr)]
            sig_tone = self._triangle(250, tone_t)
            env_tone = np.exp(-tone_t * 25) # Fast decay
            
            # Noise Component
            noise = self._noise(len(t))
            # Highpass at 1000Hz (Simple RC implementation or biquad)
            sos = scipy.signal.butter(2, 1000, 'hp', fs=self.sr, output='sos')
            noise_filt = scipy.signal.sosfilt(sos, noise)
            env_noise = np.exp(-t * 15)
            
            # Combine
            # Pad tone to match full length
            full_tone = np.zeros(len(t))
            full_tone[:len(sig_tone)] = sig_tone * env_tone * 0.5
            
            sig_noise = noise_filt * env_noise * 0.8
            
            return (full_tone + sig_noise) * velocity

        elif instrument_id in ['ch', 'oh']:
            dur = 0.4 if instrument_id == 'oh' else 0.05
            t = self._time_array(dur)
            
            # Metallic noise (random)
            noise = self._noise(len(t))
            sos = scipy.signal.butter(2, 7000, 'hp', fs=self.sr, output='sos')
            sig = scipy.signal.sosfilt(sos, noise)
            
            env = np.exp(-t * (10 if instrument_id == 'oh' else 50))
            return sig * env * 0.6 * velocity

        elif instrument_id in ['lt', 'mt', 'ht']:
            base_freq = {'lt': 80, 'mt': 120, 'ht': 180}[instrument_id]
            dur = 0.4
            t = self._time_array(dur)
            
            # Sweep
            freq = (base_freq * 1.5) * ((base_freq * 0.8)/(base_freq * 1.5))**(t/0.3)
            sig = np.sin(2 * np.pi * np.cumsum(freq) / self.sr)
            
            env = np.exp(-t * 10)
            return sig * env * 0.8 * velocity
            
        return np.zeros(100)

    def render_note(self, note, duration, preset, velocity=0.8):
        freq = 440 * 2**((note - 69) / 12)
        # Add slight release tail
        total_dur = duration + 0.2 
        t = self._time_array(total_dur)
        
        # Envelopes (Ad-hoc matching JS)
        if preset == 'piano':
             # Triangle, Lowpass Sweep (simulated by mixing sine/tri?)
             # Let's use Triangle + Exp Decay
             sig = self._triangle(freq, t)
             # Env: Attack 0.01, Decay 2.0
             env = np.ones_like(t)
             atk_len = int(0.01 * self.sr)
             env[:atk_len] = np.linspace(0, 1, atk_len)
             env[atk_len:] = np.exp(-(t[atk_len:] - t[atk_len]) * 2.0)
             
             # Filter simulation: Mix stronger fundamental over time? 
             # For speed, simple static lowpass is better than complex filtering per note
             # But here we stick to pure waveform + envelope
             return sig * env * velocity

        elif preset == 'strings':
            # Sawtooth, Slow Attack
            sig = self._saw(freq, t)
            env = np.ones_like(t)
            # Attack 0.5s
            atk_len = int(0.5 * self.sr)
            if atk_len > len(t): atk_len = len(t)
            env[:atk_len] = np.linspace(0, 1, atk_len)
            
            # Release at end of 'duration'
            rel_start = int(duration * self.sr)
            if rel_start < len(t):
                env[rel_start:] *= np.linspace(1, 0, len(t)-rel_start)
                
            return sig * env * 0.5 * velocity

        elif preset == 'guitar':
            # Sawtooth, Pluck Env
            sig = self._saw(freq, t)
            env = np.ones_like(t)
            atk_len = int(0.01 * self.sr)
            env[:atk_len] = np.linspace(0, 1, atk_len)
            env[atk_len:] = np.exp(-(t[atk_len:] - t[atk_len]) * 3.0) # Faster decay
            return sig * env * velocity

        elif preset == 'square': # Mono Lead
            sig = self._square(freq, t)
            env = np.ones_like(t)
            atk_len = int(0.02 * self.sr)
            env[:atk_len] = np.linspace(0, 1, atk_len)
            
            rel_start = int(duration * self.sr)
            if rel_start < len(t):
                 env[rel_start:] *= np.linspace(1, 0, len(t)-rel_start)
            return sig * env * velocity

        elif preset == 'sawtooth': # Mono Bass
            sig = self._saw(freq, t)
            env = np.ones_like(t)
            atk_len = int(0.02 * self.sr)
            env[:atk_len] = np.linspace(0, 1, atk_len)
            
            rel_start = int(duration * self.sr)
            if rel_start < len(t):
                 env[rel_start:] *= np.linspace(1, 0, len(t)-rel_start)
            return sig * env * velocity
            
        else: # Default Sine
            sig = self._sine(freq, t)
            env = np.ones_like(t)
            rel_start = int(duration * self.sr)
            if rel_start < len(t):
                 env[rel_start:] *= np.linspace(1, 0, len(t)-rel_start)
            return sig * velocity * env

    # --- Sequencer ---

    def render_midi(self, midi_path, instrument_type):
        """
        Parses MIDI and returns a mixed numpy audio array.
        instrument_type: 'drum', 'piano', 'mono_bass', 'mono_lead', 'poly_strings', 'poly_guitar'
        """
        try:
            mid = mido.MidiFile(midi_path)
            # Find length
            length_sec = mid.length + 2.0
            total_samples = int(length_sec * self.sr)
            master_mix = np.zeros(total_samples)
            
            # Map presets
            preset = 'sine'
            is_drum = False
            
            if instrument_type == 'drums':
                is_drum = True
            elif instrument_type == 'piano':
                preset = 'piano'
            elif instrument_type == 'bass':
                preset = 'sawtooth'
            elif instrument_type == 'guitar':
                preset = 'guitar'
            elif instrument_type == 'vocals':
                preset = 'square' # Mono Lead for Vocals
            elif instrument_type == 'other':
                preset = 'strings'
            
            # Iterate Tracks
            for track in mid.tracks:
                current_time = 0
                active_notes = {} # note -> start_sample
                
                for msg in track:
                    dt_sec = mido.tick2second(msg.time, mid.ticks_per_beat, mido.bpm2tempo(120)) # Using 120 assumption if tempo missing, usually fine for relative
                    # Wait, careful with tempo. mido handles message time if file is type 0/1 correctly?
                    # msg.time is delta ticks.
                    # We need absolute time in seconds.
                    pass
            
            # Robust Iteration using mido play-like logic
            # or converting ticks to seconds accumulating tempo changes.
            current_time = 0.0
            
            # We'll use a simplified iterator that handles tempo if possible, or just raw tick conversion
            # Since these are generated stems, tempo might be fixed or simple.
            
            for msg in mid: # This iterates over all messages in order with correct timing "deltas" in seconds!
                current_time += msg.time
                
                if msg.type == 'note_on' and msg.velocity > 0:
                    start_sample = int(current_time * self.sr)
                    
                    if is_drum:
                        # Map Midi Note to Instrument Key
                        # 36=Kick, 38=Snare, 42=CH, 46=OH, 45=LT, 47=MT, 50=HT
                        # Simple Mapping
                        drm = None
                        n = msg.note
                        if n == 36: drm = 'kick'
                        elif n == 38: drm = 'snare'
                        elif n == 42: drm = 'ch'
                        elif n == 46: drm = 'oh'
                        elif n == 45: drm = 'lt'
                        elif n == 47: drm = 'mt'
                        elif n == 50: drm = 'ht'
                        
                        if drm:
                            chunk = self.render_drum(drm, msg.velocity/127.0)
                            # Add to mix
                            end = start_sample + len(chunk)
                            if end > len(master_mix):
                                # Extend if needed (rare if length calc ok)
                                padding = np.zeros(end - len(master_mix))
                                master_mix = np.concatenate([master_mix, padding])
                            
                            master_mix[start_sample:end] += chunk
                            
                    else:
                        # Note On
                        active_notes[msg.note] = (start_sample, msg.velocity)
                        
                elif (msg.type == 'note_off' or (msg.type == 'note_on' and msg.velocity == 0)):
                    if msg.note in active_notes:
                        start_s, vel = active_notes.pop(msg.note)
                        # Render
                        dur = current_time - (start_s / self.sr)
                        if dur < 0.05: dur = 0.05 # Minimum click
                        
                        chunk = self.render_note(msg.note, dur, preset, vel/127.0)
                        end = start_s + len(chunk)
                        
                        if end > len(master_mix):
                             padding = np.zeros(end - len(master_mix))
                             master_mix = np.concatenate([master_mix, padding])
                        
                        # Add (Polyphony implies summing)
                        master_mix[start_s:end] += chunk

            # Normalize and Int16 Check
            max_val = np.max(np.abs(master_mix))
            if max_val > 0:
                master_mix = master_mix / max_val * 0.9 # -1dB
                
            return master_mix

        except Exception as e:
            print(f"PySynth Error: {e}")
            return np.zeros(1024)

def render_to_file(midi_path, wav_path, instrument_type):
    synth = PySynth()
    audio = synth.render_midi(midi_path, instrument_type)
    scipy.io.wavfile.write(wav_path, 44100, (audio * 32767).astype(np.int16))

if __name__ == "__main__":
    # Test
    # render_to_file("test.mid", "test.wav", "piano")
    pass
