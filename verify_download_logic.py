
import os
import shutil
import uuid
import time
import threading

# Simulation of the logic in main.py v4.44

def test_download_logic():
    print("--- STARTING DOWNLOAD LOGIC TEST ---")
    
    # 1. Create a dummy "source" file (simulating snata output)
    source_filename = f"test_source_{uuid.uuid4().hex}.wav"
    # Make it reasonably big (e.g. 5MB) to test streaming
    print(f"1. Creating dummy source file: {source_filename} (5MB)...")
    with open(source_filename, 'wb') as f:
        f.write(os.urandom(5 * 1024 * 1024))
    
    # Simulate strict permissions (read-only for owner) to test chmod
    os.chmod(source_filename, 0o400)
    print(f"   Created. Permissions: {oct(os.stat(source_filename).st_mode)}")

    temp_safe_path = ""
    try:
        # --- THE LOGIC FROM MAIN.PY ---
        print("\n2. EXECUTING v4.44 LOGIC (Copy + Chmod + Stream Generator)...")
        
        # A. Copy to temp file
        temp_safe_path = f"stream_test_{uuid.uuid4().hex}.wav"
        print(f"   Copying {source_filename} -> {temp_safe_path}...")
        shutil.copyfile(source_filename, temp_safe_path)
        
        # B. Chmod
        print(f"   Applying chmod 0o666 to {temp_safe_path}...")
        os.chmod(temp_safe_path, 0o666)
        
        # C. Generator
        print("   Initializing Generator...")
        def generate(path_to_stream):
            try:
                with open(path_to_stream, 'rb') as f:
                    while True:
                        chunk = f.read(16384) # 16KB chunks
                        if not chunk: break
                        yield chunk
            finally:
                # Cleanup
                print(f"   [Generator] Cleanup: Removing {path_to_stream}")
                try: os.remove(path_to_stream)
                except Exception as e: print(f"Cleanup Error: {e}")

        # D. Consume the stream (Simulate Flask Response)
        print("\n3. CONSUMING STREAM (Simulating User Download)...")
        gen = generate(temp_safe_path)
        total_bytes = 0
        start_time = time.time()
        
        for chunk in gen:
            total_bytes += len(chunk)
            # simulate network delay slightly? no, let's just blast it.
        
        duration = time.time() - start_time
        print(f"   Stream Complete! Read {total_bytes} bytes in {duration:.4f}s.")
        
        # Verify Cleanup
        if not os.path.exists(temp_safe_path):
             print("   SUCCESS: Temp file was auto-removed.")
        else:
             print("   FAILURE: Temp file still exists!")

    except Exception as e:
        print(f"\n!!! TEST FAILED with Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Cleanup source
        if os.path.exists(source_filename):
            os.remove(source_filename)
        # Cleanup temp (if test failed before generator cleanup)
        if os.path.exists(temp_safe_path):
            try: os.remove(temp_safe_path)
            except: pass
            
    print("\n--- TEST COMPLETE ---")

if __name__ == "__main__":
    test_download_logic()
