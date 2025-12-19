
import os
import time
import requests

MUSICAI_SDK_AVAILABLE = False
try:
    import musicai_sdk
    MUSICAI_SDK_AVAILABLE = True
except ImportError:
    pass

class MusicAiProcessor:
    def __init__(self, api_key):
        if not MUSICAI_SDK_AVAILABLE:
             raise ImportError("musicai_sdk not installed")
        
        # Init Client
        if hasattr(musicai_sdk, 'MusicAiClient'):
             self.client = musicai_sdk.MusicAiClient(api_key=api_key)
        else:
             # Fallback/Reflection if package name varies
             clients = [x for x in dir(musicai_sdk) if 'Client' in x]
             if clients:
                 self.client = getattr(musicai_sdk, clients[0])(api_key=api_key)
             else:
                 raise ImportError("MusicAiClient not found")

    def upload(self, file_path):
        print(f"   > Uploading {os.path.basename(file_path)}...", flush=True)
        if hasattr(self.client, 'upload_file'):
            return self.client.upload_file(file_path)
        raise NotImplementedError("Client has no upload_file")

    def run_p10no_job(self, input_url, workflow_slug="p10nofinal"):
        print(f"   > Starting Job (workflow: {workflow_slug})...", flush=True)
        # Assuming param 'Piano_MDUrl' is correct based on original p10np.py
        job = self.client.add_job(
            job_name="P10NO-Final",
            workflow_slug=workflow_slug,
            params={'Piano_MDUrl': input_url} 
        )
        
        job_id = job.get('id') if isinstance(job, dict) else getattr(job, 'id')
        print(f"     Job ID: {job_id}. Waiting...", flush=True)
        
        while True:
            status = self.client.get_job(job_id)
            if isinstance(status, dict):
                 s_str = status.get('status')
                 results = status.get('result') or status.get('outputs')
            else:
                 s_str = getattr(status, 'status', 'UNKNOWN')
                 results = getattr(status, 'result', {}) or getattr(status, 'outputs', {})

            if s_str == 'SUCCEEDED':
                return results
            elif s_str == 'FAILED':
                raise Exception(f"Job Failed: {status}")
            time.sleep(5)

    def download_file(self, url, output_path):
        r = requests.get(url)
        with open(output_path, 'wb') as f:
            f.write(r.content)
