import musicai_sdk
import sys
import json
import os

# --- Config ---
API_KEY = os.environ.get("MUSICAI_API_KEY")
JOB_ID = "12b2d092-0089-4743-a3d7-b955c5143834" # Failed Drumscribe job (kwargs)

def inspect_job():
    print(f"--- Inspecting Job {JOB_ID} ---", flush=True)
    try:
        if hasattr(musicai_sdk, 'MusicAiClient'):
             client = musicai_sdk.MusicAiClient(api_key=API_KEY)
        else:
             clients = [x for x in dir(musicai_sdk) if 'Client' in x]
             client = getattr(musicai_sdk, clients[0])(api_key=API_KEY)
        
        job = client.get_job(JOB_ID)
        print(f"Job Type: {type(job)}", flush=True)
        print(f"Job Dir: {dir(job)}", flush=True)
        if isinstance(job, dict):
             print(f"--- Job Dictionary Keys ---", flush=True)
             for k in job.keys():
                 print(f"Key: {k}", flush=True)
                 
             if 'result' in job:
                 print("--- Result Keys ---", flush=True)
                 res = job['result']
                 if isinstance(res, dict):
                     for k in res.keys():
                         print(f"Result Key: {k}", flush=True)
                     if 'outputs' in res:
                         print(f"Result Outputs: {res['outputs']}", flush=True)
                 else:
                     print(f"Result: {res}", flush=True)
                     
             if 'error' in job and job['error']:
                 print(f"\n[!] Job Error: {job['error']}", flush=True)

             if 'outputs' in job:
                  print(f"--- Job Outputs Found ---", flush=True)
                  print(f"{job['outputs']}", flush=True)
        else:
             print(f"Job is not dict: {type(job)}")
        
    except Exception as e:
        print(f"[!] Error: {e}", flush=True)

if __name__ == "__main__":
    inspect_job()
