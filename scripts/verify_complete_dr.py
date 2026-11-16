import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile
import uuid
import psycopg2

from app.core.config import settings

def run_complete_dr_drill():
    print("=================================================================")
    print("FINTRUST RAG — COMPLETE APPLICATION DISASTER RECOVERY DRILL")
    print("=================================================================")

    # 1. Inspect live production database and storage
    conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Seed a full sample record set with files if none exist
    test_tenant_id = str(uuid.uuid4())
    test_user_id = str(uuid.uuid4())
    test_doc_id = str(uuid.uuid4())
    test_ver_id = str(uuid.uuid4())
    
    cur.execute("SELECT id FROM roles WHERE id = 'ADMIN';")
    if not cur.fetchone():
        cur.execute("INSERT INTO roles (id, description) VALUES ('ADMIN', 'Admin') ON CONFLICT DO NOTHING;")

    cur.execute("""
        INSERT INTO tenants (id, name, slug, is_active, created_at, updated_at)
        VALUES (%s, 'DR Verification Bank', %s, true, NOW(), NOW());
    """, (test_tenant_id, f"dr-slug-{test_tenant_id[:8]}"))

    cur.execute("""
        INSERT INTO users (id, tenant_id, email, hashed_password, full_name, is_active, created_at, updated_at)
        VALUES (%s, %s, %s, 'hashed_dr_pass', 'DR Auditor', true, NOW(), NOW());
    """, (test_user_id, test_tenant_id, f"dr_user_{test_user_id[:8]}@fintrust.ai"))

    # Create dummy stored file in storage/documents
    doc_content = b"# Master DR Regulatory Document\n\nPreserved across complete system wipe and restoration."
    doc_hash = hashlib.sha256(doc_content).hexdigest()
    
    storage_base = Path("storage/documents")
    storage_base.mkdir(parents=True, exist_ok=True)
    stored_file_path = storage_base / f"{test_doc_id}_{doc_hash}.txt"
    with open(stored_file_path, "wb") as f:
        f.write(doc_content)

    cur.execute("""
        INSERT INTO documents (id, tenant_id, title, original_filename, mime_type, file_size_bytes, content_hash, classification, category, current_version_num, status, created_at, updated_at)
        VALUES (%s, %s, 'DR Master Doc', 'dr_master.txt', 'text/plain', %s, %s, 'CONFIDENTIAL', 'REGULATORY_COMPLIANCE', 1, 'INDEXED', NOW(), NOW());
    """, (test_doc_id, test_tenant_id, len(doc_content), doc_hash))

    cur.execute("""
        INSERT INTO document_versions (id, document_id, version_num, storage_path, total_pages, total_chunks, created_at)
        VALUES (%s, %s, 1, %s, 1, 1, NOW());
    """, (test_ver_id, test_doc_id, str(stored_file_path)))

    cur.execute("""
        INSERT INTO document_chunks (id, tenant_id, document_id, document_version_id, chunk_index, content, token_count, content_hash, embedding, created_at)
        VALUES (%s, %s, %s, %s, 0, 'Preserved chunk across DR restoration.', 6, %s, %s::vector, NOW());
    """, (str(uuid.uuid4()), test_tenant_id, test_doc_id, test_ver_id, doc_hash, "[" + ",".join("0.01" for _ in range(384)) + "]"))

    cur.execute("""
        INSERT INTO audit_logs (id, tenant_id, action, resource_type, resource_id, status, details, created_at)
        VALUES (%s, %s, 'DR_TEST_ACTION', 'DOCUMENT', %s, 'SUCCESS', '{"test": true}', NOW());
    """, (str(uuid.uuid4()), test_tenant_id, test_doc_id))

    cur.execute("""
        INSERT INTO agentic_workflows (id, tenant_id, user_id, task_type, workflow_status, approval_status, query, iteration_count, max_iterations, total_tokens_used, execution_latency_ms, created_at, updated_at)
        VALUES (%s, %s, %s, 'REGULATORY_COMPLIANCE', 'COMPLETED', 'APPROVED', 'Audit DR compliance', 1, 3, 150, 45.2, NOW(), NOW());
    """, (str(uuid.uuid4()), test_tenant_id, test_user_id))

    print("[+] Seeded comprehensive DR test dataset into PostgreSQL & filesystem.")
    cur.close()
    conn.close()

    # 2. Step 1 of DR: Create Database and Storage Snapshots
    backup_dir = Path("backups/dr_drill")
    backup_dir.mkdir(parents=True, exist_ok=True)
    db_dump_file = backup_dir / "dr_db_snapshot.dump"
    storage_tar_file = backup_dir / "dr_storage_snapshot.tar.gz"

    print(f"[*] Step 1: Taking PostgreSQL snapshot to {db_dump_file}...")
    pg_dump_bin = str(Path(r"C:\Users\ansuj\AppData\Local\pgsql\bin\pg_dump.exe"))
    env = os.environ.copy()
    if settings.POSTGRES_PASSWORD:
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

    subprocess.run([
        pg_dump_bin,
        "-h", settings.POSTGRES_SERVER,
        "-p", str(settings.POSTGRES_PORT),
        "-U", settings.POSTGRES_USER,
        "-F", "c",
        "-b",
        "-f", str(db_dump_file),
        settings.POSTGRES_DB
    ], env=env, check=True)

    print(f"[*] Step 2: Taking Storage directory snapshot to {storage_tar_file}...")
    with tarfile.open(storage_tar_file, "w:gz") as tar:
        tar.add("storage/documents", arcname="documents")

    print("[+] Snapshots generated.")

    # 3. Step 3: Perform Complete Isolated Restoration Drill
    target_dr_db = "fintrust_complete_dr_verify"
    target_dr_storage = Path("storage/dr_verified_recovery")
    if target_dr_storage.exists():
        shutil.rmtree(target_dr_storage)
    target_dr_storage.mkdir(parents=True, exist_ok=True)

    print(f"[*] Step 3: Restoring database snapshot into isolated DB '{target_dr_db}'...")
    # Ensure database exists
    admin_conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname="postgres"
    )
    admin_conn.autocommit = True
    admin_cur = admin_conn.cursor()
    admin_cur.execute(f'DROP DATABASE IF EXISTS "{target_dr_db}";')
    admin_cur.execute(f'CREATE DATABASE "{target_dr_db}";')
    admin_cur.close()
    admin_conn.close()

    # Pre-enable pgvector
    dr_conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=target_dr_db
    )
    dr_conn.autocommit = True
    dr_cur = dr_conn.cursor()
    dr_cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    dr_cur.close()
    dr_conn.close()

    # Restore DB via pg_restore
    pg_restore_bin = str(Path(r"C:\Users\ansuj\AppData\Local\pgsql\bin\pg_restore.exe"))
    proc = subprocess.run([
        pg_restore_bin,
        "-h", settings.POSTGRES_SERVER,
        "-p", str(settings.POSTGRES_PORT),
        "-U", settings.POSTGRES_USER,
        "-d", target_dr_db,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        str(db_dump_file)
    ], env=env, capture_output=True, text=True)
    print(f"[+] pg_restore returned exit code {proc.returncode}")

    print(f"[*] Step 4: Restoring storage directory into {target_dr_storage}...")
    with tarfile.open(storage_tar_file, "r:gz") as tar:
        tar.extractall(path=str(target_dr_storage))

    # 4. Step 5: Verify Complete Data & File Integrity
    print("[*] Step 5: Verifying restored database and file hashes...")
    verify_conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=target_dr_db
    )
    verify_cur = verify_conn.cursor()

    # 1. Verify extension
    verify_cur.execute("SELECT extversion FROM pg_extension WHERE extname = 'vector';")
    vec_ver = verify_cur.fetchone()
    assert vec_ver is not None, "pgvector extension missing in restored DB!"
    print(f"    [+] pgvector active: version {vec_ver[0]}")

    # 2. Verify all tables
    verify_cur.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public';")
    tables = [r[0] for r in verify_cur.fetchall()]
    print(f"    [+] Total restored tables: {len(tables)} ({', '.join(tables)})")
    assert len(tables) >= 11, f"Expected at least 11 tables, got {len(tables)}"

    # 3. Verify Document file hash and disk presence
    verify_cur.execute("SELECT id, content_hash FROM documents WHERE id = %s;", (test_doc_id,))
    doc_row = verify_cur.fetchone()
    assert doc_row is not None, "Document record not restored!"
    expected_hash = doc_row[1]

    restored_file = target_dr_storage / "documents" / f"{test_doc_id}_{doc_hash}.txt"
    assert restored_file.exists(), f"Restored file missing on disk: {restored_file}"
    
    with open(restored_file, "rb") as f:
        restored_hash = hashlib.sha256(f.read()).hexdigest()
    assert restored_hash == expected_hash, f"Hash mismatch! DB: {expected_hash}, Disk: {restored_hash}"
    print(f"    [+] File on disk verified: SHA-256 matches DB content_hash ({restored_hash})")

    # 4. Verify vector embeddings in restored table
    verify_cur.execute("SELECT count(*), vector_dims(embedding) FROM document_chunks WHERE document_id = %s GROUP BY vector_dims(embedding);", (test_doc_id,))
    chunk_meta = verify_cur.fetchone()
    assert chunk_meta[0] >= 1, "Chunks not restored!"
    assert chunk_meta[1] == 384, f"Embedding dimension mismatch: expected 384, got {chunk_meta[1]}"
    print(f"    [+] Vector embeddings verified: {chunk_meta[0]} chunks with dimension {chunk_meta[1]}")

    # 5. Verify audit logs & agentic workflows
    verify_cur.execute("SELECT count(*) FROM audit_logs WHERE tenant_id = %s;", (test_tenant_id,))
    audit_count = verify_cur.fetchone()[0]
    assert audit_count >= 1, "Audit logs not restored!"
    print(f"    [+] Audit logs verified: {audit_count} records")

    verify_cur.execute("SELECT count(*) FROM agentic_workflows WHERE tenant_id = %s;", (test_tenant_id,))
    wf_count = verify_cur.fetchone()[0]
    assert wf_count >= 1, "Agentic workflows not restored!"
    print(f"    [+] Agentic workflows verified: {wf_count} records")

    verify_cur.close()
    verify_conn.close()

    # 5. Clean up drill resources
    print("[*] Cleaning up isolated DR verification resources...")
    admin_conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname="postgres"
    )
    admin_conn.autocommit = True
    admin_cur = admin_conn.cursor()
    admin_cur.execute(f'DROP DATABASE IF EXISTS "{target_dr_db}";')
    admin_cur.close()
    admin_conn.close()

    shutil.rmtree(target_dr_storage)
    shutil.rmtree(backup_dir)

    # Clean up test rows in original database
    conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("DELETE FROM agentic_workflows WHERE tenant_id = %s;", (test_tenant_id,))
    cur.execute("DELETE FROM audit_logs WHERE tenant_id = %s;", (test_tenant_id,))
    cur.execute("DELETE FROM document_chunks WHERE tenant_id = %s;", (test_tenant_id,))
    cur.execute("DELETE FROM document_versions WHERE document_id = %s;", (test_doc_id,))
    cur.execute("DELETE FROM documents WHERE id = %s;", (test_doc_id,))
    cur.execute("DELETE FROM users WHERE tenant_id = %s;", (test_tenant_id,))
    cur.execute("DELETE FROM tenants WHERE id = %s;", (test_tenant_id,))
    cur.close()
    conn.close()
    if stored_file_path.exists():
        stored_file_path.unlink()

    print("\n[SUCCESS] COMPLETE APPLICATION DISASTER RECOVERY DRILL VERIFIED 100%!")

if __name__ == "__main__":
    run_complete_dr_drill()
