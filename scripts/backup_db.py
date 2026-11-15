import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from app.core.config import settings


def find_pg_tool(tool_name: str) -> str:
    """Finds PostgreSQL binary in standard locations or PATH."""
    local_pg_bin = Path(r"C:\Users\ansuj\AppData\Local\pgsql\bin") / f"{tool_name}.exe"
    if local_pg_bin.exists():
        return str(local_pg_bin)
    return tool_name


def backup_database(
    output_dir: str = "backups",
    pg_dump_bin: str = None,
    keep_last: int = 5
) -> Path:
    """Creates a timestamped, verified PostgreSQL backup and metadata manifest."""
    dump_exe = pg_dump_bin or find_pg_tool("pg_dump")
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup_file = out_path / f"fintrust_backup_{timestamp}.dump"
    meta_file = out_path / f"fintrust_backup_{timestamp}.json"

    print(f"[*] Starting backup of database '{settings.POSTGRES_DB}'...")
    print(f"[*] Target backup file: {backup_file}")

    env = os.environ.copy()
    if settings.POSTGRES_PASSWORD:
        env["PGPASSWORD"] = settings.POSTGRES_PASSWORD

    # Use custom archive format (-Fc) which supports pg_restore, parallel restore, and compression
    cmd = [
        dump_exe,
        "-h", settings.POSTGRES_SERVER,
        "-p", str(settings.POSTGRES_PORT),
        "-U", settings.POSTGRES_USER,
        "-F", "c",
        "-b",  # include large objects
        "-v",  # verbose
        "-f", str(backup_file),
        settings.POSTGRES_DB
    ]

    try:
        proc = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
    except subprocess.CalledProcessError as e:
        print(f"[!] Backup failed with code {e.returncode}: {e.stderr}", file=sys.stderr)
        raise

    if not backup_file.exists() or backup_file.stat().st_size == 0:
        raise RuntimeError("Backup file was not created or is empty.")

    # Compute SHA-256 checksum for integrity verification
    with open(backup_file, "rb") as f:
        file_hash = hashlib.sha256(f.read()).hexdigest()

    metadata = {
        "database": settings.POSTGRES_DB,
        "host": settings.POSTGRES_SERVER,
        "port": settings.POSTGRES_PORT,
        "user": settings.POSTGRES_USER,
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "backup_file": str(backup_file.name),
        "file_size_bytes": backup_file.stat().st_size,
        "sha256": file_hash,
        "format": "custom_archive_v1"
    }

    with open(meta_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"[+] Backup completed successfully!")
    print(f"[+] Size: {metadata['file_size_bytes']} bytes")
    print(f"[+] SHA-256: {metadata['sha256']}")
    print(f"[+] Metadata: {meta_file}")

    # Retention cleanup
    all_backups = sorted(out_path.glob("fintrust_backup_*.dump"), key=os.path.getmtime, reverse=True)
    if len(all_backups) > keep_last:
        for old in all_backups[keep_last:]:
            old_meta = old.with_suffix(".json")
            print(f"[*] Purging old backup per retention policy: {old.name}")
            try:
                old.unlink()
                if old_meta.exists():
                    old_meta.unlink()
            except Exception as ex:
                print(f"[!] Warning purging {old}: {ex}")

    return backup_file


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="FinTrust Database Backup Utility")
    parser.add_argument("--output-dir", default="backups", help="Directory to store backup files")
    parser.add_argument("--keep", type=int, default=5, help="Number of recent backups to retain")
    args = parser.parse_args()

    backup_database(output_dir=args.output_dir, keep_last=args.keep)
