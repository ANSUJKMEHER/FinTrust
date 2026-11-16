import subprocess
import urllib.request
import urllib.error
import json

def create_repo():
    # 1. Get credentials from git credential helper
    proc = subprocess.run(
        ['git', 'credential', 'fill'],
        input='protocol=https\nhost=github.com\n',
        capture_output=True,
        text=True,
        check=True
    )
    creds = dict(line.split('=', 1) for line in proc.stdout.strip().split('\n') if '=' in line)
    token = creds.get('password')
    username = creds.get('username')
    print(f"Retrieved credentials for user: {username}")

    repo_name = "FinTrust"
    url = "https://api.github.com/user/repos"
    payload = json.dumps({
        "name": repo_name,
        "description": "FinTrust RAG — Enterprise Financial Intelligence & Compliance Platform (PostgreSQL pgvector, Google Gemini 2.5 Flash, Hybrid RRF, LangGraph Multi-Agent, React MD3)",
        "private": False,
        "has_issues": True,
        "has_wiki": True
    }).encode()

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "FinTrust-Deployer"
        }
    )

    try:
        with urllib.request.urlopen(req) as resp:
            res = json.loads(resp.read().decode())
            html_url = res.get("html_url")
            print(f"Repository successfully created: {html_url}")
            return html_url
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        if e.code == 422 and "name already exists" in err_body:
            repo_url = f"https://github.com/{username}/{repo_name}"
            print(f"Repository {repo_name} already exists at {repo_url}!")
            return repo_url
        else:
            print(f"HTTP Error {e.code}: {err_body}")
            raise

if __name__ == "__main__":
    create_repo()
