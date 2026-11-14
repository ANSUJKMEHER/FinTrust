import subprocess
import sys


def test_alembic_migrations_offline_sql_generation():
    """Test 14: Verifies that Alembic migration scripts compile and generate valid DDL without syntax errors."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Alembic offline SQL generation failed:\n{result.stderr}"
    sql_output = result.stdout
    assert "CREATE TABLE tenants" in sql_output
    assert "CREATE TABLE roles" in sql_output
    assert "CREATE TABLE users" in sql_output
    assert "CREATE TABLE documents" in sql_output
    assert "CREATE TABLE document_versions" in sql_output
    assert "CREATE TABLE document_permissions" in sql_output
    assert "CREATE TABLE audit_logs" in sql_output
