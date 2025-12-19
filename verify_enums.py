try:
    from roex_python.models.mixing import InstrumentGroup, MusicalStyle, PresenceSetting, PanPreference, ReverbPreference

    print("\n--- ReverbPreference Members ---")
    for member in ReverbPreference:
        print(f"{member.name} = {member.value}")

    print("\n--- PanPreference Members ---")
    print("\n--- PanPreference Members ---")
    for member in PanPreference:
        print(f"{member.name} = {member.value}")

    print("\n--- PresenceSetting Members ---")
    for member in PresenceSetting:
        print(f"{member.name} = {member.value}")

    print("\n--- InstrumentGroup Members ---")
    for member in InstrumentGroup:
        print(f"{member.name} = {member.value}")
        
    print("\n--- MusicalStyle Members ---")
    for member in MusicalStyle:
        print(f"{member.name}")

    print("\n--- Checking for OTHER ---")
    if hasattr(InstrumentGroup, 'OTHER'):
        print("InstrumentGroup.OTHER exists.")
    else:
        print("InstrumentGroup.OTHER does NOTE exist.")

except ImportError as e:
    print(f"Import failed: {e}")
except Exception as e:
    print(f"Error: {e}")
