import subprocess
import urllib.request
import json
import sys

def get_token():
    proc = subprocess.run(
        ['git', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n',
        capture_output=True,
        text=True,
        check=True
    )
    creds = dict(line.split('=', 1) for line in proc.stdout.strip().split('\n') if '=' in line)
    return creds.get('password'), creds.get('username', 'ANSUJKMEHER')

class NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_headers = dict(req.headers)
        if 'Authorization' in new_headers:
            del new_headers['Authorization']
        return urllib.request.Request(newurl, headers=new_headers, origin_req_host=req.origin_req_host, unverifiable=True)

def get_job_logs(job_id):
    token, username = get_token()
    opener = urllib.request.build_opener(NoRedirectHandler)
    req = urllib.request.Request(
        f'https://api.github.com/repos/{username}/FinTrust/actions/jobs/{job_id}/logs',
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'FinTrust-CI'
        }
    )
    with opener.open(req) as resp:
        return resp.read().decode('utf-8', errors='replace').splitlines()

logs = get_job_logs(133243269690)
for idx in range(540, min(len(logs), 660)):
    print(f"{idx}: {logs[idx]}")
