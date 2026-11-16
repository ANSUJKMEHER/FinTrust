import json
import urllib.parse
import urllib.request

def test_live_system():
    base_url = "http://127.0.0.1:8000"

    # 1. Health check
    req = urllib.request.Request(f"{base_url}/health/ready")
    with urllib.request.urlopen(req) as resp:
        health = json.loads(resp.read().decode())
    print("[1] Health Check /health/ready:", health)

    # 2. Login
    login_data = json.dumps({
        "email": "admin@fintrust.com",
        "password": "FinTrustAdmin2026!",
        "tenant_slug": "fintrust-demo"
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/login",
        data=login_data,
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as resp:
        token_data = json.loads(resp.read().decode())
    token = token_data["access_token"]
    print("[2] Login Successful! JWT Access Token received.")

    # 3. User Profile
    req = urllib.request.Request(
        f"{base_url}/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        user = json.loads(resp.read().decode())
    print(f"[3] Authenticated Profile: {user['full_name']} | Roles: {user['roles']}")

    # 4. List Documents
    req = urllib.request.Request(
        f"{base_url}/api/v1/documents/",
        headers={"Authorization": f"Bearer {token}"}
    )
    with urllib.request.urlopen(req) as resp:
        docs = json.loads(resp.read().decode())
    print(f"[4] Documents in Tenant ({len(docs)} found):")
    for d in docs:
        print(f"    - [{d['status']}] {d['title']} ({d['category']})")

    # 5. Grounded RAG Query
    rag_payload = json.dumps({
        "query": "What are the mandatory SAR filing thresholds and deadlines?",
        "top_k": 5
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/api/v1/rag/query",
        data=rag_payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req) as resp:
        rag_res = json.loads(resp.read().decode())
    print("\n[5] Grounded RAG Query Result:")
    print("    - Query:", "What are the mandatory SAR filing thresholds and deadlines?")
    print("    - Grounded Response:", rag_res.get("answer", ""))
    print("    - Citations count:", len(rag_res.get("citations", [])))
    for cit in rag_res.get("citations", []):
        snippet = cit.get("matched_text") or cit.get("snippet") or cit.get("content") or str(cit)
        print(f"      * Citation: {snippet[:80]}...")
    print("    - Estimated Cost ($):", rag_res.get("estimated_cost", 0.0))

    # 6. Multi-Agent Compliance Audit
    agent_payload = json.dumps({
        "query": "Audit SAR filing deadlines and transaction thresholds under FinCEN statutory framework",
        "statute_reference": "31 CFR Chapter X",
        "require_human_approval": False
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/api/v1/agentic/compliance-audit",
        data=agent_payload,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    )
    with urllib.request.urlopen(req) as resp:
        agent_res = json.loads(resp.read().decode())
    print("\n[6] Agentic Compliance Workflow:")
    print("    - Workflow ID:", agent_res.get("workflow_id"))
    print("    - Task Type:", agent_res.get("task_type"))
    print("    - Status:", agent_res.get("workflow_status"))
    print("    - Total Tokens Used:", agent_res.get("total_tokens_used", 0))
    print("    - Total Estimated Cost ($):", agent_res.get("total_estimated_cost", 0.0))
    print("    - Final Report Excerpt:", str(agent_res.get("final_report", ""))[:200] + "...")

if __name__ == "__main__":
    test_live_system()
