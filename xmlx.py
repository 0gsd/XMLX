"""
xmlx.py - XML Metadata Generator (v2.55)

Generates the .xml metadata files used by the application to index/serve generated audio content.

AGENT NOTE (Monkey-Patch):
- We patch `scipy.signal.hann` on import because the installed version of Librosa
  relies on a deprecated/removed Scipy attribute. Removing this patch will cause
  XML generation crashes.
"""
import os
import datetime
import librosa
import numpy as np
try:
    import scipy.signal
    if not hasattr(scipy.signal, 'hann'):
        import scipy.signal.windows
        scipy.signal.hann = scipy.signal.windows.hann
except ImportError:
    pass

def generate_xml(
    input_wav,
    output_xml_path,
    final_mix_path=None,
    stems=None, # dict: { 'category': {'audio': path, 'midi': path, 'render': path} }
    transcodes=None, # list of paths
    base_url=None
):
    """
    Generates an XMLX file for the given processing result.
    """
    # Resolve Base URL (Env Var > Arg > Default)
    if base_url is None:
        base_url = os.environ.get('XMLX_BASE_URL', "https://xmlx.app")
    
    # --- Analysis ---
    duration_str = "00:00:00.000"
    bpm_str = "120"
    key_str = "Am"
    sample_rate_str = "44100"
    
    try:
        y, sr = librosa.load(input_wav, sr=None)
        
        # Duration
        dur_sec = librosa.get_duration(y=y, sr=sr)
        # Format HH:MM:SS.mmm
        m, s = divmod(dur_sec, 60)
        h, m = divmod(m, 60)
        duration_str = "{:02d}:{:02d}:{:06.3f}".format(int(h), int(m), s)
        sample_rate_str = str(sr)

        # BPM (Simple)
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)
        if tempo is not None:
            # Handle numpy scalar/array return
            t_val = float(tempo) if np.ndim(tempo) == 0 else float(tempo[0])
            bpm_str = f"{int(round(t_val))}"
            
    except Exception as e:
        print(f"[XMLX] Analysis failed: {e}")

    # --- XML Construction ---
    
    filename = os.path.basename(input_wav)
    title = os.path.splitext(filename)[0]
    xml_dir = os.path.dirname(output_xml_path)
    
    # Helper for Paths (Attributes): Relative path from XML file
    def format_path(p):
        if not p: return ""
        try:
            return os.path.relpath(p, xml_dir)
        except:
            return os.path.basename(p)

    # Helper for URLs (CDATA): Full Download URL
    def format_url(p):
        if not p: return ""
        # Assuming the XML is at the root of the serving folder or relative to it
        # We construct the URL relative to the XML file location
        rel = format_path(p)
        from urllib.parse import quote
        # Quote ensures spaces and chars are safe
        base = base_url.rstrip('/')
        return f"{base}/download/{quote(rel)}"

    # Helper for CDATA Wrapper (Manual Input)
    def wrap_manual_cdata(content):
        return f"$$<![CDATA[{content}]]>$$"

    # Helper for Derived CDATA (Populated, No $$)
    def wrap_derived_cdata(content):
        return f"<![CDATA[{content}]]>"

    xml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<XMLX version="1.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
  
  <Song id="$$unique_song_id$$" sequence="$$1$$">
    
    <InLine>
      
      <Metadata>
        <Title>{title}</Title>
        <Version>$$Original Mix$$</Version>
        <Duration>{duration_str}</Duration>
        
        <ISRC>$$US-XYZ-24-00001$$</ISRC>
        <ISWC>$$T-123.456.789-0$$</ISWC>
        <UPC>$$123456789012$$</UPC>
        
        <ReleaseDate>$${datetime.date.today().isoformat()}$$</ReleaseDate>
        <Explicit>$$false$$</Explicit>
        <Language>$$en$$</Language>
        <BPM>{bpm_str.replace('$$','')}</BPM>
        <Key>{key_str.replace('$$','')}</Key>
        
        <Credits>
          <Credit role="Main Artist">$$Artist Name$$</Credit>
          <Credit role="Producer">Uncanny Mixer (XMlX)</Credit>
        </Credits>

        <MoreInfoURL>https://xmlx.app</MoreInfoURL>
      </Metadata>

      <AudioMaster>
        <RootFile type="audio/wav" sampleRate="{sample_rate_str}" bitDepth="16">
          {wrap_derived_cdata(format_url(input_wav))}
        </RootFile>

        {f'''<DerivedFile type="audio/wav" usage="neural_mix" description="Neural Mix">
            {wrap_derived_cdata(format_url(final_mix_path))}
        </DerivedFile>''' if final_mix_path else ''}

        <Transcodes>
          <!-- derived examples -->
        </Transcodes>
      </AudioMaster>

      <Stems>"""

    if stems:
        for cat, files in stems.items():
            cat_upper = cat.upper()
            xml_content += f"""
        <Stem category="{cat_upper}">"""
            
            if files.get('audio'):
                 xml_content += f"""
          <Audio type="audio/wav">
            {wrap_derived_cdata(format_url(files['audio']))}
          </Audio>"""
            
            if files.get('midi'):
                 xml_content += f"""
          <Midi type="audio/midi">
            {wrap_derived_cdata(format_url(files['midi']))}
          </Midi>"""
            
            if files.get('render'):
                 xml_content += f"""
          <Render type="audio/wav">
            {wrap_derived_cdata(format_url(files['render']))}
          </Render>"""
            
            xml_content += """
        </Stem>"""

    xml_content += """
      </Stems>

      <Accoutrements>
        <Notes>
          $$<![CDATA[
            Generated by XMlX.app
          ]]>$$
        </Notes>
      </Accoutrements>

    </InLine>
  </Song>
</XMLX>
"""

    with open(output_xml_path, 'w') as f:
        f.write(xml_content)
    try: os.chmod(output_xml_path, 0o644)
    except: pass
    
    print(f"[OUTPUT] XML Metadata|{output_xml_path}")
