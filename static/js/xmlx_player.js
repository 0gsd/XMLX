/**
 * xmlx_player.js
 * The "Brain" of the XML0X Audio Player.
 * Handles XMLX parsing, Audio/MIDI syncing, and Playback State.
 */

class XMLXPlayer {
    constructor(synth) {
        this.synth = synth; // Xmlynth instance
        this.ctx = synth.ctx;

        // State
        this.isPlaying = false;
        this.songData = null; // Parsed XML info
        this.stems = {}; // { name: { audioElem, midiData, mode: 'audio'|'midi', ... } }

        // Sync
        this.startTime = 0;
        this.lookahead = 0.1; // 100ms
        this.scheduleAheadTime = 0.1;
        this.nextNoteTime = 0.0;
        this.notePtrs = {}; // { stemName: nextEventIndex }
        this.timerID = null;

        // Hooks for UI updates
        this.onTimeUpdate = null;
        this.onStemUpdate = null; // triggers UI refresh of rack
    }

    async loadXML(url) {
        console.log(`[XMLX] Loading: ${url}`);
        try {
            const resp = await fetch(url);
            const text = await resp.text();
            const parser = new DOMParser();
            const xmlDoc = parser.parseFromString(text, "text/xml");

            this.songData = {
                title: url.split('/').pop(), // simplistic
                xmlDoc: xmlDoc
            };

            // Parse Stems
            this.stems = {};
            const stemNodes = xmlDoc.getElementsByTagName("Stem");

            // Parallel loading of assets? For v1, sequential is fine.
            for (let node of stemNodes) {
                const name = node.getAttribute("name");
                const audioSrc = node.getElementsByTagName("Audio")[0]?.textContent;
                const midiSrc = node.getElementsByTagName("Midi")[0]?.textContent;

                this.stems[name] = {
                    name: name,
                    audioSrc: audioSrc,
                    midiSrc: midiSrc,
                    mode: 'audio', // default
                    instId: this.assignDefaultInstrument(name),
                    audioElem: null,
                    midiData: null
                };

                // Preload Audio Element
                if (audioSrc) {
                    const audio = new Audio(audioSrc);
                    audio.crossOrigin = "anonymous"; // needed for WebAudio connections?
                    // Connect to WebAudio graph if we want filters/analysers later.
                    // For perfect sync, we might need MediaElementSource.
                    const source = this.ctx.createMediaElementSource(audio);
                    source.connect(this.ctx.destination); // or master gain
                    this.stems[name].audioElem = audio;
                    this.stems[name].audioSourceNode = source;
                }

                // Preload MIDI Data via API
                if (midiSrc) {
                    // Fetch parsed JSON from backend
                    // Assuming midiSrc is like "/tmp/wavF/..." or absolute. 
                    // API expects 'path'.
                    const apiUrl = `/api/xml0x/parse_midi?path=${encodeURIComponent(midiSrc)}`;
                    try {
                        const mResp = await fetch(apiUrl);
                        if (mResp.ok) {
                            const mJson = await mResp.json();
                            this.stems[name].midiData = mJson.events;
                            // console.log(`[XMLX] Loaded MIDI for ${name}: ${mJson.events.length} events`);
                        }
                    } catch (e) {
                        console.warn(`[XMLX] Failed loading MIDI for ${name}`, e);
                    }
                }
            }

            if (this.onStemUpdate) this.onStemUpdate(this.stems);
            return true;

        } catch (e) {
            console.error("[XMLX] Load Failed", e);
            return false;
        }
    }

    assignDefaultInstrument(stemName) {
        const map = { 'piano': 0, 'bass': 6, 'drums': 9, 'vocals': 2, 'guitar': 5, 'other': 1 };
        return map[stemName.toLowerCase()] || 0;
    }

    play() {
        if (this.ctx.state === 'suspended') this.ctx.resume();

        this.isPlaying = true;
        this.startTime = this.ctx.currentTime;

        // Reset MIDI Pointers
        for (let k in this.stems) this.notePtrs[k] = 0;

        // Start Audio Stems (if in audio mode)
        for (let k in this.stems) {
            const s = this.stems[k];
            if (s.mode === 'audio' && s.audioElem) {
                // Ideally, seek to 0 first
                s.audioElem.currentTime = 0;
                s.audioElem.play();
            }
        }

        // Start Scheduler
        this.scheduler();
    }

    pause() {
        this.isPlaying = false;
        clearTimeout(this.timerID);

        // Pause Audio
        for (let k in this.stems) {
            const s = this.stems[k];
            if (s.audioElem) s.audioElem.pause();
            // Kill MIDI voices?
            // synth.panic() or similar?
            // For now, let envelopes release naturally.
        }
    }

    toggleStemMode(name) {
        const s = this.stems[name];
        if (!s) return;

        // Toggle
        const newMode = s.mode === 'audio' ? 'midi' : 'audio';

        // Check availability
        if (newMode === 'midi' && !s.midiData) {
            console.warn("No MIDI data for stem " + name);
            return;
        }
        if (newMode === 'audio' && !s.audioElem) return;

        s.mode = newMode;

        // Apply immediately if playing
        if (this.isPlaying) {
            if (s.mode === 'audio') {
                // Sync Audio to current time
                // Use Master clock (currentTime - startTime)
                const seekPos = this.ctx.currentTime - this.startTime;
                if (s.audioElem) {
                    s.audioElem.currentTime = seekPos;
                    s.audioElem.play();
                }
            } else {
                if (s.audioElem) s.audioElem.pause();
                // MIDI will be picked up by scheduler automatically
                // We need to set the pointer though?
                // No, scheduler checks absolute time, just need to find the right index.
                // Optimization: Scan forward in MIDI data to match current time.
                this.syncMidiPointer(name, this.ctx.currentTime - this.startTime);
            }
        }

        if (this.onStemUpdate) this.onStemUpdate(this.stems);
    }

    changeInstrument(name, instId) {
        if (this.stems[name]) {
            this.stems[name].instId = instId;
            if (this.onStemUpdate) this.onStemUpdate(this.stems);
        }
    }

    // --- Internal Scheduler ---

    syncMidiPointer(name, timeInSong) {
        // Fast forward pointer to current time
        const s = this.stems[name];
        if (!s.midiData) return;

        let ptr = 0;
        while (ptr < s.midiData.length && s.midiData[ptr].t < timeInSong) {
            ptr++;
        }
        this.notePtrs[name] = ptr;
    }

    scheduler() {
        if (!this.isPlaying) return;

        // Schedule loop
        const now = this.ctx.currentTime;
        const timeInSong = now - this.startTime;

        // Emit UI time update
        if (this.onTimeUpdate) this.onTimeUpdate(timeInSong);

        // For each stem in MIDI mode
        for (let k in this.stems) {
            const s = this.stems[k];
            if (s.mode !== 'midi' || !s.midiData) continue;

            let ptr = this.notePtrs[k];

            // Look ahead
            while (ptr < s.midiData.length) {
                const event = s.midiData[ptr];

                // If event is within scheduling window
                if (event.t >= timeInSong && event.t < timeInSong + this.scheduleAheadTime) {
                    // Calc precise trigger time
                    const triggerTime = this.startTime + event.t;
                    // Trigger
                    this.scheduleEvent(s, event, triggerTime);
                    ptr++;
                } else if (event.t < timeInSong) {
                    // Late event? Skip.
                    ptr++;
                } else {
                    // Future event outside window
                    break;
                }
            }
            this.notePtrs[k] = ptr;
        }

        // Call next tick
        this.timerID = setTimeout(() => this.scheduler(), 25);
    }

    scheduleEvent(stem, event, when) {
        // We only handle NOTE ON here to simplify (synth handles duration/off? No, we need note off)
        // XML0X API returns { type: 'on'|'off', n: note, v: vel }
        // Xmlynth logic: noteOn(inst, note, vel). noteOff(inst, note).

        // We can use setTimeout for exact triggering or pass 'when' if synth supports scheduling?
        // Xmlynth `noteOn` uses `ctx.currentTime` internally. Let's patch it or use setTimeout delay.

        const delay = (when - this.ctx.currentTime) * 1000;
        if (delay < 0) return; // missed it

        setTimeout(() => {
            if (event.type === 'on') {
                this.synth.noteOn(stem.instId, event.n, event.v);
            } else {
                this.synth.noteOff(stem.instId, event.n);
            }
        }, delay);

        // Note: setTimeout is not sample-accurate. 
        // Better: Update Xmlynth to accept `startTime` arg.
        // But for v1.6 and "Winamp vibe", this is acceptable.
    }
}
