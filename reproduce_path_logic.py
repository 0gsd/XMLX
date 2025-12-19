
import os
import sys

# Simulation Configuration
WAV_F_FOLDER = "/tmp/wavF" # Simulate Cloud Run path
os.makedirs(WAV_F_FOLDER, exist_ok=True)
dummy_file = os.path.join(WAV_F_FOLDER, "test_file.wav")
with open(dummy_file, 'w') as f:
    f.write("test content")

def test_resolve(filename):
    print(f"--- Resolving: '{filename}' ---")
    try:
        root_dir = os.path.realpath(WAV_F_FOLDER)
        
        # Logic from main.py
        filename = os.path.normpath(filename)
        
        if filename.startswith("/"):
            filename = filename[1:]
            
        rel_root = str(root_dir).lstrip('/')
        print(f"   Root Dir: {root_dir}")
        print(f"   Rel Root: {rel_root}")
        
        if filename.startswith(rel_root):
             print(f"   -> Starts with Rel Root")
             filename = filename[len(rel_root):].lstrip('/')
             
        print(f"   Final Filename component: {filename}")

        full_path = os.path.join(root_dir, filename)
        full_path = os.path.realpath(full_path)
        
        print(f"   Resolved Path: {full_path}")
        
        if not full_path.startswith(root_dir):
             print(f"   [!] Security Alert: Path traversal")
             return
             
        if os.path.exists(full_path):
            print(f"   [OK] File exists.")
        else:
            print(f"   [MISSING] File not found.")

    except Exception as e:
        print(f"   [ERROR] {e}")

# Test Cases
test_resolve("test_file.wav")
test_resolve("tmp/wavF/test_file.wav") # Simulate double pathing
test_resolve("/tmp/wavF/test_file.wav")
test_resolve("../wavF/test_file.wav")
