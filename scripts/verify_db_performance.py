import math
import random
import time
import uuid
import psycopg2
from app.core.config import settings

def run_db_performance_analysis():
    print("[*] Connecting to PostgreSQL 16...")
    conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB
    )
    conn.autocommit = True
    cur = conn.cursor()

    # Create isolated benchmark tenant
    bench_tenant_id = str(uuid.uuid4())
    bench_doc_id = str(uuid.uuid4())
    bench_ver_id = str(uuid.uuid4())

    print(f"[*] Seeding benchmark dataset for tenant {bench_tenant_id}...")
    cur.execute("""
        INSERT INTO tenants (id, name, slug, is_active, created_at, updated_at)
        VALUES (%s, 'Benchmark Scaling Bank', %s, true, NOW(), NOW())
        ON CONFLICT DO NOTHING;
    """, (bench_tenant_id, f"bench-scale-{bench_tenant_id[:8]}"))

    cur.execute("""
        INSERT INTO documents (id, tenant_id, title, original_filename, mime_type, file_size_bytes, content_hash, classification, category, current_version_num, status, created_at, updated_at)
        VALUES (%s, %s, 'Regulatory Master Corpus', 'corpus.txt', 'text/plain', 50000, %s, 'INTERNAL', 'REGULATORY_COMPLIANCE', 1, 'INDEXED', NOW(), NOW())
        ON CONFLICT DO NOTHING;
    """, (bench_doc_id, bench_tenant_id, uuid.uuid4().hex))

    cur.execute("""
        INSERT INTO document_versions (id, document_id, version_num, storage_path, total_pages, total_chunks, created_at)
        VALUES (%s, %s, 1, 'corpus.txt', 50, 500, NOW())
        ON CONFLICT DO NOTHING;
    """, (bench_ver_id, bench_doc_id))

    # Generate 500 synthetic regulatory chunks with 384-dimensional normalized vector embeddings
    sample_terms = [
        "suspicious activity report filing deadline 30 days",
        "currency transaction report threshold exceeding 10000 dollars",
        "bank secrecy act anti money laundering compliance policy",
        "customer due diligence beneficial ownership identification",
        "office of foreign assets control sanctions screening",
        "capital adequacy liquidity coverage ratio basel iii framework",
        "finCEN confidential compliance investigation audit trail"
    ]

    print("[*] Inserting 500 chunks with 384-d embeddings...")
    chunk_rows = []
    for i in range(500):
        c_id = str(uuid.uuid4())
        text_content = f"{random.choice(sample_terms)} Clause {i} specifying regulatory obligations and statutory requirements."
        # Generate random normalized 384-d vector
        raw_vec = [random.gauss(0, 1) for _ in range(384)]
        norm = math.sqrt(sum(x*x for x in raw_vec))
        norm_vec = [x / norm for x in raw_vec]
        vec_str = "[" + ",".join(f"{x:.6f}" for x in norm_vec) + "]"
        c_hash = uuid.uuid4().hex
        chunk_rows.append((c_id, bench_tenant_id, bench_doc_id, bench_ver_id, i, text_content, 25, c_hash, vec_str))

    args_str = b",".join(
        cur.mogrify("(%s, %s, %s, %s, %s, %s, %s, %s, %s::vector, NOW())", r) for r in chunk_rows
    ).decode("utf-8")

    cur.execute(f"""
        INSERT INTO document_chunks (id, tenant_id, document_id, document_version_id, chunk_index, content, token_count, content_hash, embedding, created_at)
        VALUES {args_str}
    """)
    print("[+] 500 chunks inserted.")

    # Run VACUUM ANALYZE so PostgreSQL planner statistics reflect the new data
    print("[*] Running VACUUM ANALYZE document_chunks...")
    cur.execute("VACUUM ANALYZE document_chunks;")

    query_vec = "[" + ",".join("0.05" for _ in range(384)) + "]"

    print("\n=======================================================")
    print("TEST 1: Vector Search Plan with Default Planner Settings")
    print("=======================================================")
    cur.execute(f"""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT id, chunk_index, 1 - (embedding <=> '{query_vec}'::vector) AS cosine_sim
        FROM document_chunks
        WHERE tenant_id = '{bench_tenant_id}'
        ORDER BY embedding <=> '{query_vec}'::vector
        LIMIT 10;
    """)
    for line in cur.fetchall():
        print(line[0])

    print("\n=======================================================")
    print("TEST 2: Vector Search Plan with enable_seqscan = OFF")
    print("=======================================================")
    cur.execute("SET enable_seqscan = off;")
    cur.execute(f"""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT id, chunk_index, 1 - (embedding <=> '{query_vec}'::vector) AS cosine_sim
        FROM document_chunks
        ORDER BY embedding <=> '{query_vec}'::vector
        LIMIT 10;
    """)
    for line in cur.fetchall():
        print(line[0])
    cur.execute("RESET enable_seqscan;")

    print("\n=======================================================")
    print("TEST 3: Full-Text Search Plan (GIN index on search_vector)")
    print("=======================================================")
    cur.execute(f"""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT id, chunk_index, ts_rank_cd(search_vector, to_tsquery('english', 'sanctions & screening')) AS fts_rank
        FROM document_chunks
        WHERE search_vector @@ to_tsquery('english', 'sanctions & screening')
          AND tenant_id = '{bench_tenant_id}'
        ORDER BY fts_rank DESC
        LIMIT 10;
    """)
    for line in cur.fetchall():
        print(line[0])

    print("\n=======================================================")
    print("TEST 4: Compound Tenant Filtering (B-Tree on tenant_id, document_id)")
    print("=======================================================")
    cur.execute(f"""
        EXPLAIN (ANALYZE, BUFFERS)
        SELECT id, chunk_index, section_heading
        FROM document_chunks
        WHERE tenant_id = '{bench_tenant_id}' AND document_id = '{bench_doc_id}'
        ORDER BY chunk_index ASC
        LIMIT 50;
    """)
    for line in cur.fetchall():
        print(line[0])

    # Clean up benchmark tenant
    print("\n[*] Cleaning up benchmark tenant data...")
    cur.execute("DELETE FROM document_chunks WHERE tenant_id = %s;", (bench_tenant_id,))
    cur.execute("DELETE FROM document_versions WHERE document_id = %s;", (bench_doc_id,))
    cur.execute("DELETE FROM documents WHERE id = %s;", (bench_doc_id,))
    cur.execute("DELETE FROM tenants WHERE id = %s;", (bench_tenant_id,))
    cur.execute("VACUUM ANALYZE document_chunks;")
    print("[+] Benchmark data cleaned up.")

    cur.close()
    conn.close()

if __name__ == "__main__":
    run_db_performance_analysis()
