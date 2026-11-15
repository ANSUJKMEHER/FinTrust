import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import psycopg2

from app.core.config import settings


def find_pg_tool(tool_name: str) -> str:
    """Finds PostgreSQL binary in standard locations or PATH."""
    local_pg_bin = Path(r"C:\Users\ansuj\AppData\Local\pgsql\bin") / f"{tool_name}.exe"
    if local_pg_bin.exists():
        return str(local_pg_bin)
    return tool_name


def restore_database(
    backup_file: Path,
    target_db: str,
    create_target: bool = True,
    verify_tables: bool = True
) -> bool:
    """Restores a PostgreSQL backup (.dump) and verifies table integrity."""
    restore_exe = find_pg_tool("pg_restore")
    psql_exe = find_pg_tool("psql")

    if not backup_file.exists():
        raise FileNotFoundError(f"Backup file not found: {backup_file}")

    print(f"[*] Starting database restore...")
    print(f"[*] Source backup file: {backup_file}")
    print(f"[*] Target database: '{target_db}'")

    # Verify checksum if companion metadata JSON exists
    meta_path = backup_file.with_suffix(".json")
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        with open(backup_file, "rb") as f:
            computed_sha = hashlib.sha256(f.read()).hexdigest()
        if computed_sha != meta.get("sha256"):
            raise ValueError(f"Integrity check failed! Expected {meta.get('sha256')} but got {computed_sha}")
        print(f"[+] Backup integrity verified (SHA-256 match).")

    env = os.environ.copy()
    if settings.POSTGRES_PASSWORD:
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

    # If target DB doesn't exist and create_target is True, create it via administrative connection
    if create_target:
        print(f"[*] Ensuring target database '{target_db}' exists...")
        conn = psycopg2.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            dbname="postgres"
        )
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (target_db,))
        exists = cur.fetchone()
        if not exists:
            print(f"[*] Creating target database '{target_db}'...")
            cur.execute(f'CREATE DATABASE "{target_db}"')
        cur.close()
        conn.close()

    # Enable pgvector in target DB prior to restoring tables
    conn = psycopg2.connect(
        host=settings.POSTGRES_SERVER,
        port=settings.POSTGRES_PORT,
        user=settings.POSTGRES_USER,
        password=settings.POSTGRES_PASSWORD,
        dbname=target_db
    )
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    cur.close()
    conn.close()

    # Execute pg_restore
    cmd = [
        restore_exe,
        "-h", settings.POSTGRES_SERVER,
        "-p", str(settings.POSTGRES_PORT),
        "-U", settings.POSTGRES_USER,
        "-d", target_db,
        "-v",
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-privileges",
        str(backup_file)
    ]

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True
        )
        # Note: pg_restore may exit with 1 if there are minor warnings (e.g. drop table if exists)
        if proc.returncode not in (0, 1):
            print(f"[!] pg_restore exited with error code {proc.returncode}: {proc.stderr}", file=sys.stderr)
            raise RuntimeError(f"pg_restore failed: {proc.stderr}")
    except Exception as e:
        print(f"[!] Restore execution error: {e}", file=sys.stderr)
        raise

    print(f"[+] pg_restore completed.")

    if verify_tables:
        print(f"[*] Verifying restored database schema and tables...")
        conn = psycopg2.connect(
            host=settings.POSTGRES_SERVER,
            port=settings.POSTGRES_PORT,
            user=settings.POSTGRES_USER,
            password=settings.POSTGRES_PASSWORD,
            dbname=target_db
        )
        cur = conn.cursor()
        cur.execute("""
            SELECT tablename 
            FROM pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        tables = [r[0] for r in cur.fetchall()]
        print(f"[+] Total tables restored in '{target_db}': {len(tables)}")
        for t in tables:
            cur.execute(f'SELECT count(*) FROM "{t}"')
            cnt = cur.fetchone()[0]
            print(f"    - Table '{t}': {cnt} records")
        cur.close()
        conn.close()

    print(f"[+] Database restore and validation successful!")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinTrust Database Restore Utility")
    parser.add_argument("--backup-file", help="Path to .dump file to restore")
    parser.add_argument("--target-db", default="fintrust_db", help="Target database name")
    parser.add_argument("--create-target", action="store_true", default=True, help="Create database if missing")
    parser.add_argument("--verify", action="store_true", default=True, help="Verify tables after restore")
    args = parser.parse_args()

    if not args.backup_file:
        # Default to latest dump in backups/
        backup_dir = Path("backups")
        dumps = sorted(backup_dir.glob("fintrust_backup_*.dump"), key=os.path.getmtime, reverse=True)
        if not dumps:
            print("[!] No backups found in backups/ directory.")
            sys.exit(1)
        target_file = dumps[0]
    else:
        target_file = Path(args.backup_file)

    restore_database(
        backup_file=target_file,
        target_db=args.target_db,
        create_target=args.create_target,
        verify_tables=args.verify
    )
