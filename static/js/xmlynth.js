/**
 * xmlynth.js (or xmlynth1.0.js)
 * A hybrid dual-voice synthesizer using Virtual Analog approximations of General MIDI tones.
 * * Features:
 * - 10 Custom "Xmlnstruments" (5 Poly, 5 Mono).
 * - Dual-layer architecture (Voice A + Voice B).
 * - Cross-Modulation (FM), Filtering, and independent ADSR.
 * - Pure Web Audio API (No external assets).
 */

class Xmlynth {
    constructor() {
        this.ctx = new (window.AudioContext || window.webkitAudioContext)();
        this.masterGain = this.ctx.createGain();
        this.masterGain.gain.value = 0.4; // Safety headroom
        this.masterGain.connect(this.ctx.destination);

        // Active voices registry
        this.activeVoices = {};

        // Monophonic voice tracker (keeps track of the last played note per channel)
        this.monoTracker = {};

        // --- THE 128 GM TONE APPROXIMATIONS (Virtual Analog Recipes) ---
        // Maps GM Program # to oscillator types and base envelope characteristics.
        this.gmRecipes = {
            // PIANOS & KEYS
            0: { type: 'triangle', shape: 'plucked', bright: 0.6 }, // Acoustic Grand
            4: { type: 'sine', shape: 'tine', bright: 0.8 }, // E. Piano 1
            7: { type: 'sawtooth', shape: 'funky', bright: 1.0 }, // Clavinet
            19: { type: 'sine', shape: 'organ', bright: 0.5 }, // Church Organ

            // CHROMATIC PERC
            9: { type: 'triangle', shape: 'bell', bright: 1.0 }, // Glockenspiel
            14: { type: 'triangle', shape: 'bell', bright: 0.9, detune: 5 }, // Tubular Bells

            // GUITARS & BASS
            29: { type: 'square', shape: 'sustain', bright: 0.8 }, // Overdriven Guitar
            30: { type: 'sawtooth', shape: 'sustain', bright: 0.9, dist: true }, // Distortion Guitar
            37: { type: 'sawtooth', shape: 'snap', bright: 0.7 }, // Slap Bass 1
            38: { type: 'sawtooth', shape: 'bass', bright: 0.2 }, // Synth Bass 1
            39: { type: 'square', shape: 'bass', bright: 0.3 }, // Synth Bass 2

            // STRINGS & ORCHESTRA
            45: { type: 'square', shape: 'pluck', bright: 0.6 }, // Pizzicato
            48: { type: 'sawtooth', shape: 'pad', bright: 0.4 }, // String Ensemble 1
            50: { type: 'sawtooth', shape: 'pad', bright: 0.5 }, // Synth Strings 1
            52: { type: 'triangle', shape: 'voice', bright: 0.3 }, // Choir Aahs

            // BRASS & REEDS
            56: { type: 'sawtooth', shape: 'brass', bright: 0.8 }, // Trumpet
            73: { type: 'triangle', shape: 'wind', bright: 0.2 }, // Flute
            77: { type: 'sawtooth', shape: 'wind', bright: 0.1 }, // Shakuhachi

            // SYNTH LEAD/PAD
            80: { type: 'square', shape: 'lead', bright: 0.7 }, // Lead 1 (Square)
            81: { type: 'sawtooth', shape: 'lead', bright: 0.8 }, // Lead 2 (Sawtooth)

            // DRUMS (Synthesized)
            116: { type: 'sine', shape: 'perc', bright: 0.1 } // Taiko Drum
        };

        // --- THE 10 XMLNSTRUMENTS ---
        // 0-4: Polyphonic | 5-9: Monophonic
        this.instruments = [
            // POLYPHONIC
            {
                name: "Celestial Keys",
                poly: true,
                voiceA: 0,  // Piano
                voiceB: 48, // Strings
                mix: 0.6,   // 60% Piano, 40% Strings
                filter: { type: 'lowpass', freq: 2500, Q: 1 },
                mod: { type: 'mix', amount: 0 }, // Simple layer
                adsr: { a: 0.01, d: 0.3, s: 0.6, r: 0.5 }
            },
            {
                name: "Crystal Pad",
                poly: true,
                voiceA: 4,  // E.Piano
                voiceB: 9,  // Glockenspiel
                mix: 0.5,
                filter: { type: 'highpass', freq: 200, Q: 0 },
                mod: { type: 'ring', amount: 0.2 }, // Light Ring Mod
                adsr: { a: 0.1, d: 0.5, s: 0.4, r: 1.5 }
            },
            {
                name: "Dark Choir",
                poly: true,
                voiceA: 52, // Choir
                voiceB: 19, // Organ
                mix: 0.7,
                filter: { type: 'lowpass', freq: 800, Q: 2 },
                mod: { type: 'fm', amount: 50 }, // Slight FM for grit
                adsr: { a: 0.6, d: 0.2, s: 0.8, r: 1.0 }
            },
            {
                name: "Retro Brass",
                poly: true,
                voiceA: 56, // Trumpet
                voiceB: 81, // Saw Lead
                mix: 0.5,
                filter: { type: 'lowpass', freq: 1500, Q: 3 }, // Resonant
                mod: { type: 'detune', amount: 15 }, // Chorusing
                adsr: { a: 0.05, d: 0.2, s: 0.7, r: 0.2 }
            },
            {
                name: "Glass Pluck",
                poly: true,
                voiceA: 45, // Pizzicato
                voiceB: 14, // Tubular Bells
                mix: 0.4,
                filter: { type: 'bandpass', freq: 1200, Q: 5 },
                mod: { type: 'fm', amount: 200 }, // Metallic FM
                adsr: { a: 0.01, d: 0.4, s: 0.0, r: 0.4 }
            },

            // MONOPHONIC (Logic applied in noteOn)
            {
                name: "Acid Lead",
                poly: false,
                voiceA: 81, // Saw Lead
                voiceB: 30, // Distortion Gtr
                mix: 0.8,
                filter: { type: 'lowpass', freq: 600, Q: 15 }, // High Res acid
                mod: { type: 'fm', amount: 100 },
                adsr: { a: 0.01, d: 0.3, s: 0.4, r: 0.1 }
            },
            {
                name: "Funky Bass",
                poly: false,
                voiceA: 37, // Slap Bass
                voiceB: 7,  // Clavinet
                mix: 0.5,
                filter: { type: 'lowpass', freq: 800, Q: 4 },
                mod: { type: 'mix', amount: 0 },
                adsr: { a: 0.01, d: 0.2, s: 0.5, r: 0.05 }
            },
            {
                name: "Flute Solo",
                poly: false,
                voiceA: 73, // Flute
                voiceB: 77, // Shakuhachi
                mix: 0.5,
                filter: { type: 'lowpass', freq: 3000, Q: 0.5 },
                mod: { type: 'detune', amount: 8 }, // Breath flutter effect
                adsr: { a: 0.15, d: 0.1, s: 0.9, r: 0.2 }
            },
            {
                name: "Grit Lead",
                poly: false,
                voiceA: 29, // Overdriven Gtr
                voiceB: 80, // Square Lead
                mix: 0.6,
                filter: { type: 'highpass', freq: 300, Q: 2 },
                mod: { type: 'fm', amount: 350 }, // Heavy fuzz
                adsr: { a: 0.02, d: 0.1, s: 0.8, r: 0.1 }
            },
            {
                name: "Sub Kick Bass",
                poly: false,
                voiceA: 116, // Taiko
                voiceB: 39,  // Synth Bass 2
                mix: 0.4,
                filter: { type: 'lowpass', freq: 150, Q: 2 },
                mod: { type: 'fm', amount: 50 },
                adsr: { a: 0.01, d: 0.2, s: 0.0, r: 0.1 }
            }
        ];
    }

    /**
     * Initializes Audio Context (Requires user interaction usually)
     */
    init() {
        if (this.ctx.state === 'suspended') {
            this.ctx.resume();
        }
    }

    /**
     * Get list of instruments for UI
     */
    getInstrumentList() {
        return this.instruments.map((inst, idx) => ({
            id: idx,
            name: inst.name,
            type: inst.poly ? 'Poly' : 'Mono'
        }));
    }

    /**
     * Trigger a note
     * @param {number} instIndex - Instrument ID (0-9)
     * @param {number} note - MIDI Note Number (0-127)
     * @param {number} velocity - MIDI Velocity (0-127)
     */
    noteOn(instIndex, note, velocity) {
        if (velocity === 0) {
            this.noteOff(instIndex, note);
            return;
        }

        const inst = this.instruments[instIndex];
        if (!inst) return;

        // Monophonic Logic: Kill previous note on this instrument
        if (!inst.poly) {
            if (this.monoTracker[instIndex]) {
                this.stopVoice(this.monoTracker[instIndex]);
            }
        }

        const freq = 440 * Math.pow(2, (note - 69) / 12);
        const now = this.ctx.currentTime;
        const velGain = velocity / 127;

        // --- AUDIO GRAPH CONSTRUCTION ---

        // 1. Voice Source Setup
        const voiceA = this.createVoiceSource(inst.voiceA, freq);
        const voiceB = this.createVoiceSource(inst.voiceB, freq);

        // 2. Filter Setup
        const filter = this.ctx.createBiquadFilter();
        filter.type = inst.filter.type;
        filter.frequency.value = inst.filter.freq;
        filter.Q.value = inst.filter.Q;

        // Dynamic Filter Envelope (simple follower)
        filter.frequency.setValueAtTime(inst.filter.freq, now);
        filter.frequency.exponentialRampToValueAtTime(inst.filter.freq * 1.5, now + inst.adsr.a);
        filter.frequency.exponentialRampToValueAtTime(inst.filter.freq, now + inst.adsr.d);

        // 3. Modulation Routing
        if (inst.mod.type === 'fm') {
            // Cross Mod: Voice B modulates Voice A freq
            const modGain = this.ctx.createGain();
            modGain.gain.value = inst.mod.amount * 10;
            voiceB.osc.connect(modGain);
            modGain.connect(voiceA.osc.frequency);
        } else if (inst.mod.type === 'detune') {
            voiceB.osc.detune.value = inst.mod.amount;
            voiceA.osc.detune.value = -inst.mod.amount;
        }

        // 4. Mixing
        const mixNode = this.ctx.createGain();
        const gainA = this.ctx.createGain();
        const gainB = this.ctx.createGain();

        gainA.gain.value = inst.mix;
        gainB.gain.value = 1 - inst.mix;

        voiceA.osc.connect(gainA);
        voiceB.osc.connect(gainB); // If FM, B is still audible in mix unless handled otherwise, but standard here is parallel

        gainA.connect(filter);
        gainB.connect(filter);

        // 5. Amp Envelope (ADSR)
        const envelope = this.ctx.createGain();
        envelope.gain.value = 0;

        // Attack
        envelope.gain.setValueAtTime(0, now);
        envelope.gain.linearRampToValueAtTime(velGain, now + inst.adsr.a);
        // Decay/Sustain
        envelope.gain.exponentialRampToValueAtTime(velGain * inst.adsr.s + 0.01, now + inst.adsr.a + inst.adsr.d);

        filter.connect(envelope);
        envelope.connect(this.masterGain);

        // 6. Start Oscillators
        voiceA.osc.start(now);
        voiceB.osc.start(now);

        // 7. Store Voice
        const voiceId = `${instIndex}-${note}`;
        const voiceObj = {
            nodes: [voiceA.osc, voiceB.osc, gainA, gainB, filter, envelope, mixNode],
            env: envelope,
            inst: inst,
            startTime: now
        };

        this.activeVoices[voiceId] = voiceObj;

        if (!inst.poly) {
            this.monoTracker[instIndex] = voiceId;
        }
    }

    /**
     * Stop a note
     */
    noteOff(instIndex, note) {
        // For mono instruments, we might not want to kill the note immediately if legato is implemented,
        // but for this request, we just release the tracked note.
        let voiceId = `${instIndex}-${note}`;

        // If mono, handle the tracked voice regardless of note number (priority to last played)
        const inst = this.instruments[instIndex];
        if (!inst.poly) {
            voiceId = this.monoTracker[instIndex];
            this.monoTracker[instIndex] = null;
        }

        if (this.activeVoices[voiceId]) {
            this.releaseVoice(voiceId);
        }
    }

    createVoiceSource(gmNum, freq) {
        const osc = this.ctx.createOscillator();
        const recipe = this.gmRecipes[gmNum] || { type: 'sine', shape: 'sustain' };

        osc.type = recipe.type;
        osc.frequency.value = freq;
        if (recipe.detune) osc.detune.value = recipe.detune;

        // Note: In a full GM engine, we'd use PeriodicWave for complex shapes here.
        // For this chunk, standard waves + filters do the heavy lifting.
        return { osc, recipe };
    }

    releaseVoice(id) {
        const v = this.activeVoices[id];
        if (!v) return;

        const now = this.ctx.currentTime;
        const releaseTime = v.inst.adsr.r;

        // Cancel scheduled values to ensure immediate release phase
        v.env.gain.cancelScheduledValues(now);
        v.env.gain.setValueAtTime(v.env.gain.value, now);
        v.env.gain.exponentialRampToValueAtTime(0.001, now + releaseTime);

        // Cleanup nodes after release
        v.nodes.forEach(node => {
            if (node.stop) node.stop(now + releaseTime + 0.1);
        });

        // Garbage collection from registry
        setTimeout(() => {
            delete this.activeVoices[id];
        }, (releaseTime + 0.2) * 1000);
    }

    stopVoice(id) {
        if (this.activeVoices[id]) {
            this.releaseVoice(id);
        }
    }

    /**
     * Helper: Play a random instrument
     */
    playRandomNote(duration = 0.5) {
        const instId = Math.floor(Math.random() * 10);
        // Random pitch in musical range
        const pitch = 48 + Math.floor(Math.random() * 24);
        this.noteOn(instId, pitch, 100);
        setTimeout(() => this.noteOff(instId, pitch), duration * 1000);
        return { instId, pitch };
    }
}

// Export for module use, or attach to window for simple browser use
window.Xmlynth = Xmlynth;
