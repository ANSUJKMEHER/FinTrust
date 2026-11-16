import subprocess
import urllib.request
import json
import time
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

def get_recent_runs():
    token, username = get_token()
    req = urllib.request.Request(
        f'https://api.github.com/repos/{username}/FinTrust/actions/runs',
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'FinTrust-CI'
        }
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        return data.get('workflow_runs', [])

def get_run_jobs(run_id):
    token, username = get_token()
    req = urllib.request.Request(
        f'https://api.github.com/repos/{username}/FinTrust/actions/runs/{run_id}/jobs',
        headers={
            'Authorization': f'Bearer {token}',
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'FinTrust-CI'
        }
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        return data.get('jobs', [])

def check_latest_commit_runs():
    runs = get_recent_runs()
    latest_sha = subprocess.run(['git', 'rev-parse', 'HEAD'], capture_output=True, text=True).stdout.strip()
    matching_runs = [r for r in runs if r['head_sha'] == latest_sha]

    print(f"Monitoring CI for commit: {latest_sha[:7]}")
    print(f"Found {len(matching_runs)} workflow runs triggered.")

    for r in matching_runs:
        print(f"\nWorkflow: {r['name']} (ID: {r['id']})")
        print(f"Status: {r['status']} | Conclusion: {r['conclusion']}")
        jobs = get_run_jobs(r['id'])
        for j in jobs:
            print(f"  Job: {j['name']} -> {j['status']} / {j['conclusion']}")
            for s in j.get('steps', []):
                if s.get('status') == 'in_progress':
                    print(f"    ⏳ Step in progress: {s['name']}")
                elif s.get('conclusion') == 'failure':
                    print(f"    ❌ Step failed: {s['name']}")

if __name__ == '__main__':
    check_latest_commit_runs()
