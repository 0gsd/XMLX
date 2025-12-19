import sys
import roex_python

print("--- RoEx Python Inspection ---")
print(f"Location: {roex_python.__file__}")
print(f"Top-level Dir: {dir(roex_python)}")

try:
    from roex_python.enums import MusicalStyle
    print("\n[SUCCESS] Found MusicalStyle in roex_python.enums")
    print(f"Members: {[m.name for m in MusicalStyle]}")
except ImportError:
    print("\n[FAIL] Not in roex_python.enums")

try:
    import roex_python.models.mixing as mixing
    print(f"\nScanning roex_python.models.mixing: {dir(mixing)}")
    if 'MusicalStyle' in dir(mixing):
        print("[SUCCESS] Found MusicalStyle in roex_python.models.mixing")
    else:
        print("[FAIL] Not in roex_python.models.mixing")
except ImportError:
    print("\n[FAIL] Could not import roex_python.models.mixing")

# Check for 'mix' submodule
try:
    from roex_python.mix import MusicalStyle
    print("\n[SUCCESS] Found MusicalStyle in roex_python.mix")
except ImportError:
    print("\n[FAIL] Not in roex_python.mix")
