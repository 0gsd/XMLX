"""
update_version.py - Deployment Helper

Automates version bumping, file renaming, and HTML template updating for new deployments.
"""
import os
import sys
import re
import glob

def update_version(new_version, changelog_msg=None):
    print(f"Bumping to version {new_version}...")
    
    # 1. Find and Validate XML Example
    files = glob.glob("xmlx*eg.xml")
    if not files:
        print("Error: No xmlx*eg.xml found!")
        sys.exit(1)
        
    # Sort by version number extracted from filename (xmlx<VER>eg.xml)
    def get_ver(fname):
        m = re.search(r'xmlx([\d.]+)eg\.xml', fname)
        return float(m.group(1)) if m else 0.0
        
    files.sort(key=get_ver, reverse=True)
    xml_file = files[0]
    print(f"Found latest example: {xml_file}")
    
    with open(xml_file, 'r') as f:
        content = f.read()
        
    if not "<XMLX" in content:
        print("Error: XML file does not appear to contain <XMLX> root node.")
        sys.exit(1)
        
    # Update Version Attribute in XML
    new_xml_content = re.sub(r'<XMLX version="[^"]+"', f'<XMLX version="{new_version}"', content)
    
    # Rename File
    new_xml_name = f"xmlx{new_version}eg.xml"
    
    with open(new_xml_name, 'w') as f:
        f.write(new_xml_content)
        
    if new_xml_name != xml_file:
        os.remove(xml_file)
        print(f"Renamed {xml_file} -> {new_xml_name}")
    else:
        print(f"Updated content of {new_xml_name}")

    # 2. Update unified_index.html (Title and ASCII Art)
    index_path = "templates/unified_index.html"
    with open(index_path, 'r') as f:
        html = f.read()
        
    # Update Title
    html = re.sub(r'<title>XMlX.app v[^ ]+ \|', f'<title>XMlX.app v{new_version} |', html)
    
    # Update ASCII Art (naive replace of vX.X pattern at end of line, or specific search)
    # The ASCII art has "v1.7" (or similar) on a specific line.
    # Update ASCII Art (Robust match for "       vX.XX       ")
    # We look for a line containing ONLY whitespace and vX.XX, or vX.XX at specific position
    html = re.sub(r'(v\d+\.\d+)', f'v{new_version}', html, count=1) 
    # Note: potential risk if title also has vX.XX but title is handled above separately.
    # However, re.sub scans from start. The first vX.XX it finds in BODY might be the ASCII art one if we are careful.
    # Actually, let's stick to the previous logic but LOOSER.
    # We know the version is inside <pre class="ascii-art"> ... </pre> (or similar context).
    # But given the file structure, the Title tag comes first: <title>XMlX.app v4.19 | ...
    # So the *first* match of v\d+\.\d+ in the whole file is the Title. The *second* is the ASCII art.
    
    
    # Matches: <div ...>v4.33</div> (ignoring attributes)
    # Be robust: ">\s*v\d+\.\d+\s*</div>"
    # Use \g<1> to prevent \1 + 4 (from version) looking like group 14
    html = re.sub(r'(\s*v)\d+\.\d+(\s*</div>)', f'\\g<1>{new_version}\\g<2>', html)

    
    with open(index_path, 'w') as f:
        f.write(html)
    print(f"Updated {index_path}")

    # 3. Update xml0x.html (Demo Link)
    player_path = "templates/xml0x.html"
    with open(player_path, 'r') as f:
        p_html = f.read()
        
    # Update the loadXML path
    # player.loadXML('/xml0x/files/xmlx1.6eg.xml') -> ...
    p_html = re.sub(r"player\.loadXML\('/xml0x/files/xmlx[^']+'\)", 
                    f"player.loadXML('/xml0x/files/{new_xml_name}')", p_html)
                    
    with open(player_path, 'w') as f:
        f.write(p_html)
    print(f"Updated {player_path}")

    # 4. Update Changelog
    if changelog_msg:
        import datetime
        today = datetime.date.today().isoformat()
        cl_path = "changelog.md"
        
        new_entry = f"## v{new_version} ({today})\n- {changelog_msg}\n\n"
        
        if os.path.exists(cl_path):
            with open(cl_path, 'r') as f:
                current_cl = f.read()
            
            # Insert after the header (# Changelog\n) if it exists, otherwise prepend
            if "# Changelog" in current_cl:
                # robustly find the end of the header line
                parts = current_cl.split('\n', 1)
                if len(parts) > 1 and parts[0].startswith("# Changelog"):
                    final_cl = parts[0] + "\n\n" + new_entry + parts[1].lstrip()
                else:
                    final_cl = new_entry + current_cl
            else:
                final_cl = "# Changelog\n\n" + new_entry + current_cl
        else:
             final_cl = "# Changelog\n\n" + new_entry
             
        with open(cl_path, 'w') as f:
            f.write(final_cl)
        print(f"Updated {cl_path}")
    
    print("Done!")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python update_version.py <version_number> [changelog_message]")
        sys.exit(1)
    
    version = sys.argv[1]
    msg = sys.argv[2] if len(sys.argv) > 2 else None
    
    update_version(version, msg)
