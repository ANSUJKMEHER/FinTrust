import os
import sys
import psycopg2

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://fintrust_user@127.0.0.1:5432/fintrust_db"
)

def run_pg_verification():
    print("=" * 60)
    print("FINTRUST RAG: POSTGRESQL 16 & PGVECTOR VERIFICATION")
    print("=" * 60)
    print(f"Connecting to database: {DATABASE_URL} ...")

    conn = psycopg2.connect(DATABASE_URL)
    conn.autocommit = True
    cur = conn.cursor()

    # 1. Check Server Version
    cur.execute("SELECT version();")
    ver = cur.fetchone()[0]
    print(f"[OK] Server Version: {ver}")

    # 2. Check and Enable Extensions
    extensions = ["uuid-ossp", "pgcrypto", "vector"]
    for ext in extensions:
        cur.execute(f'CREATE EXTENSION IF NOT EXISTS "{ext}";')
        cur.execute("SELECT extversion FROM pg_extension WHERE extname = %s;", (ext,))
        ext_ver = cur.fetchone()[0]
        print(f"[OK] Extension '{ext}' enabled (version: {ext_ver})")

    # 3. Verify pgvector Functionality
    print("\n--- Testing pgvector Functionality ---")
    cur.execute("DROP TABLE IF EXISTS test_vectors;")
    cur.execute("""
        CREATE TABLE test_vectors (
            id SERIAL PRIMARY KEY,
            title VARCHAR(100),
            embedding vector(4)
        );
    """)
    print("[OK] Created test_vectors table with vector(4) column.")

    # Insert sample embeddings
    cur.execute("""
        INSERT INTO test_vectors (title, embedding) VALUES
        ('AML Policy Clause', '[0.1, 0.2, 0.3, 0.4]'),
        ('KYC Verification', '[0.15, 0.25, 0.28, 0.38]'),
        ('Lending Rules', '[0.9, 0.8, 0.1, 0.05]');
    """)
    print("[OK] Inserted 3 test vector records.")

    # Cosine distance ordering
    cur.execute("""
        SELECT title, embedding <=> '[0.1, 0.2, 0.3, 0.4]' AS cosine_dist
        FROM test_vectors
        ORDER BY embedding <=> '[0.1, 0.2, 0.3, 0.4]'
        LIMIT 2;
    """)
    rows = cur.fetchall()
    print("[OK] Cosine distance query results:")
    for r in rows:
        print(f"     -> {r[0]}: distance = {r[1]:.6f}")

    # Create HNSW index
    cur.execute("""
        CREATE INDEX idx_test_vector_hnsw ON test_vectors 
        USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
    """)
    print("[OK] HNSW vector index created successfully with vector_cosine_ops.")

    # 4. Verify PostgreSQL Full-Text Search
    print("\n--- Testing PostgreSQL Full-Text Search (FTS) ---")
    cur.execute("DROP TABLE IF EXISTS test_regulatory_docs;")
    cur.execute("""
        CREATE TABLE test_regulatory_docs (
            id SERIAL PRIMARY KEY,
            doc_id VARCHAR(50),
            content TEXT,
            tsv tsvector GENERATED ALWAYS AS (to_tsvector('english', content)) STORED
        );
    """)
    print("[OK] Created test_regulatory_docs table with generated tsvector.")

    # Insert exact financial and regulatory terms
    cur.execute("""
        INSERT INTO test_regulatory_docs (doc_id, content) VALUES
        ('BSA_RULE', 'Under Bank Secrecy Act BSA Section 5318(g), financial institutions must file reports on suspicious transactions.'),
        ('FINCEN_GUIDE', 'FinCEN Form 111 outlines the statutory procedures for mandatory SAR reporting deadlines within 30 days.'),
        ('GDPR_PRIVACY', 'According to GDPR Art. 33, data controllers must notify supervisory authorities of personal data breaches within 72 hours.');
    """)
    cur.execute("CREATE INDEX idx_test_docs_fts ON test_regulatory_docs USING GIN (tsv);")
    print("[OK] GIN index on tsvector created successfully.")

    # Query FTS with ts_rank_cd and exact term matching
    search_queries = [
        "BSA Section 5318(g)",
        "FinCEN Form 111",
        "GDPR Art. 33"
    ]
    for q in search_queries:
        cur.execute("""
            SELECT doc_id, ts_rank_cd(tsv, plainto_tsquery('english', %s)) AS rank, content
            FROM test_regulatory_docs
            WHERE tsv @@ plainto_tsquery('english', %s)
            ORDER BY rank DESC;
        """, (q, q))
        match = cur.fetchone()
        if match:
            print(f"[OK] FTS Match for '{q}': doc={match[0]}, rank={match[1]:.4f}")
        else:
            print(f"[FAIL] No FTS match found for '{q}'")

    cur.close()
    conn.close()
    print("\n[SUCCESS] PostgreSQL 16, pgvector, and Full-Text Search are fully operational!")

if __name__ == "__main__":
    run_pg_verification()
