import psycopg2
from app.core.config import settings

def inspect():
    conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=settings.POSTGRES_DB
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT tablename, indexname, indexdef 
        FROM pg_indexes 
        WHERE schemaname = 'public'
        ORDER BY tablename, indexname;
    """)
    rows = cur.fetchall()
    print(f"Total indexes in public schema: {len(rows)}")
    for table, idx_name, idx_def in rows:
        print(f"[{table}] {idx_name}: {idx_def}")

    # Test an EXPLAIN on vector and text search
    print("\n--- EXPLAIN QUERY EXECUTION PLAN: HYBRID RETRIEVAL ---")
    dummy_vector = "[" + ",".join(["0.01"] * 384) + "]"
    explain_sql = f"""
    EXPLAIN ANALYZE
    SELECT id, document_id, chunk_index, 
           1 - (embedding <=> '{dummy_vector}'::vector) AS cosine_sim
    FROM document_chunks
    WHERE tenant_id = '00000000-0000-0000-0000-000000000001'
    ORDER BY embedding <=> '{dummy_vector}'::vector
    LIMIT 10;
    """
    cur.execute(explain_sql)
    for line in cur.fetchall():
        print(line[0])

    conn.close()

if __name__ == "__main__":
    inspect()
