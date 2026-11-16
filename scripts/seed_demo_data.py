"""
FinTrust RAG — Seed Demo Data Script
Initializes a clean demo tenant, roles, demo users with known passwords,
and seeds rich financial and regulatory compliance documents with HNSW embeddings.
"""

from pathlib import Path
from app.db.session import SessionLocal
from app.db.models.tenant import Tenant
from app.db.models.role import Role
from app.db.models.user import User
from app.core.security import hash_password
from app.services.document_service import DocumentService
from app.services.storage_service import StorageService
from app.services.file_validation_service import FileValidationService
from app.services.ingestion_service import IngestionService
from app.schemas.document import DocumentCreate
from app.db.models.document import DocumentClassification

def seed_demo_environment():
    db = SessionLocal()
    try:
        print("[1/4] Ensuring default RBAC roles exist...")
        role_definitions = [
            ("ADMIN", "Full tenant administration and unrestricted document access"),
            ("COMPLIANCE_OFFICER", "Manage regulatory policies and compliance verification"),
            ("ANALYST", "Query authorized documents and perform financial research"),
            ("AUDITOR", "Strictly read-only access to authorized compliance documents and audit logs"),
        ]
        for role_id, desc in role_definitions:
            existing_role = db.query(Role).filter(Role.id == role_id).first()
            if not existing_role:
                db.add(Role(id=role_id, description=desc))
        db.commit()

        print("[2/4] Initializing Demo Tenant: 'FinTrust Global Financial'...")
        demo_slug = "fintrust-demo"
        tenant = db.query(Tenant).filter(Tenant.slug == demo_slug).first()
        if not tenant:
            tenant = Tenant(
                name="FinTrust Global Financial",
                slug=demo_slug,
                is_active=True
            )
            db.add(tenant)
            db.commit()
            db.refresh(tenant)
            print(f"  -> Created tenant {tenant.name} (ID: {tenant.id})")
        else:
            print(f"  -> Found existing tenant {tenant.name} (ID: {tenant.id})")

        print("[3/4] Creating Demo User Accounts...")
        role_admin = db.query(Role).filter(Role.id == "ADMIN").first()
        role_co = db.query(Role).filter(Role.id == "COMPLIANCE_OFFICER").first()
        role_analyst = db.query(Role).filter(Role.id == "ANALYST").first()
        role_auditor = db.query(Role).filter(Role.id == "AUDITOR").first()

        users_to_seed = [
            {
                "email": "admin@fintrust.com",
                "full_name": "Alexander Hamilton (Admin)",
                "password": "FinTrustAdmin2026!",
                "roles": [role_admin, role_co]
            },
            {
                "email": "compliance@fintrust.com",
                "full_name": "Claire Vance (Compliance Officer)",
                "password": "FinTrustCompliance2026!",
                "roles": [role_co]
            },
            {
                "email": "analyst@fintrust.com",
                "full_name": "Arthur Dent (Financial Analyst)",
                "password": "FinTrustAnalyst2026!",
                "roles": [role_analyst]
            },
            {
                "email": "auditor@fintrust.com",
                "full_name": "Eleanor Rigby (Internal Auditor)",
                "password": "FinTrustAuditor2026!",
                "roles": [role_auditor]
            }
        ]

        admin_user = None
        for udata in users_to_seed:
            existing_user = db.query(User).filter(User.email == udata["email"]).first()
            if not existing_user:
                new_user = User(
                    tenant_id=tenant.id,
                    email=udata["email"],
                    hashed_password=hash_password(udata["password"]),
                    full_name=udata["full_name"],
                    is_active=True,
                    roles=udata["roles"]
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                if udata["email"] == "admin@fintrust.com":
                    admin_user = new_user
                print(f"  -> Created user: {udata['email']} (Password: {udata['password']})")
            else:
                existing_user.hashed_password = hash_password(udata["password"])
                existing_user.roles = udata["roles"]
                existing_user.tenant_id = tenant.id
                db.commit()
                if udata["email"] == "admin@fintrust.com":
                    admin_user = existing_user
                print(f"  -> Updated user: {udata['email']} (Password: {udata['password']})")

        print("[4/4] Ingesting Sample Financial & Regulatory Documents...")
        sample_doc_1 = """# FinCEN Suspicious Activity Reporting (SAR) Guidance & Statutory Thresholds

## Executive Overview
Under the Bank Secrecy Act (BSA) regulations codified in 31 CFR Chapter X, financial institutions are required to report suspicious activity that may indicate money laundering, tax evasion, fraud, or terrorist financing.

## Mandatory Filing Thresholds
1. **Identified Suspect**: Any transaction conducted or attempted by, at, or through the institution involving aggregate funds or assets of **$5,000 or more**, where the bank knows, suspects, or has reason to suspect illegal activity.
2. **No Identified Suspect**: Any transaction conducted or attempted involving aggregate funds or assets of **$25,000 or more**, regardless of whether potential suspects can be identified.
3. **Insider Abuse**: Any known or suspected criminal violation, regardless of the transaction amount, involving employee or insider misconduct.

## Statutory Filing Deadlines & Record Retention
- Reports must be electronically filed through the BSA E-Filing System within **30 calendar days** following initial detection of the suspicious transaction.
- If no suspect was identified on the date of detection, the institution may take an additional **30 calendar days** (for a total of 60 days) to identify suspects before filing.
- All supporting documentation must be retained for at least **five (5) years** from the filing date and made available to FinCEN and law enforcement upon request.
- Confidentiality: Institutions and their officers, directors, and employees are strictly prohibited from disclosing to the subject that a SAR has been filed (Safe Harbor protection applies under 31 U.S.C. 5318(g)(3)).
"""

        sample_doc_2 = """# Global Alpha Fund Q3 2026 Financial Performance & Risk Management Report

## 1. Executive Portfolio Highlights
Global Alpha Fund closed Q3 2026 with Assets Under Management (AUM) of **$4.85 Billion**, representing a quarter-over-quarter expansion of **6.2%**. The net asset value (NAV) per share increased to **$142.50**.

## 2. Sector Allocation Breakdown
- **Information Technology & AI Infrastructure**: 38.5% ($1.87 Billion)
- **Financial Institutions & Fintech**: 24.0% ($1.16 Billion)
- **Healthcare & Biotechnology**: 18.2% ($882 Million)
- **Renewable Energy & Clean Tech**: 12.3% ($597 Million)
- **Cash & Cash Equivalents**: 7.0% ($340 Million)

## 3. Risk Management Metrics & Value at Risk (VaR)
- **Daily 99% Value at Risk (VaR)**: Maintained at **1.45%** ($70.3 Million), comfortably below the regulatory limit of 2.25%.
- **Sharpe Ratio (Trailing 12-Month)**: **2.18**, demonstrating robust risk-adjusted returns against benchmark S&P 500 (1.42).
- **Liquidity Coverage Ratio (LCR)**: Maintained at **148%**, exceeding the Basel III requirement of 100%.
- **Stress Test Scenario**: Modeled against a 200 bps sudden interest rate shock and a 15% equity market drawdown; projected capital adequacy remains at 16.4% Tier 1 Capital.
"""

        documents = [
            ("FinCEN_SAR_Compliance_Policy_2026.md", "FinCEN SAR Compliance Policy 2026", sample_doc_1, "REGULATORY_COMPLIANCE"),
            ("Global_Alpha_Fund_Q3_2026_Report.md", "Global Alpha Fund Q3 2026 Financial Report", sample_doc_2, "FINANCIAL_REPORT")
        ]

        doc_service = DocumentService(db)
        storage = StorageService()

        for filename, title, content, category in documents:
            file_bytes = content.encode("utf-8")
            sanitized_name, valid_mime, file_size, content_hash = FileValidationService.validate_file(
                file_bytes=file_bytes,
                filename=filename,
                content_type="text/markdown"
            )

            # Check if already exists in tenant
            existing = doc_service.repo.get_by_content_hash_in_tenant(content_hash, tenant.id)
            if existing:
                print(f"  -> Document already exists: '{title}' (ID: {existing.id}, Status: {existing.status})")
                continue

            saved_path = storage.save_file(
                tenant_id=tenant.id,
                content_hash=content_hash,
                extension=Path(sanitized_name).suffix,
                file_bytes=file_bytes
            )

            doc = doc_service.create_document(
                DocumentCreate(
                    title=title,
                    original_filename=sanitized_name,
                    mime_type=valid_mime,
                    file_size_bytes=file_size,
                    content_hash=content_hash,
                    classification=DocumentClassification.INTERNAL,
                    category=category,
                    storage_path=str(saved_path)
                ),
                admin_user
            )

            version_id = doc.versions[0].id
            ingestion = IngestionService(db)
            ingestion.process_document(doc.id, version_id, saved_path)
            db.refresh(doc)
            print(f"  -> Successfully Ingested & Indexed: '{title}' (ID: {doc.id}, Status: {doc.status})")

        print("\nSeed completed successfully!")
    finally:
        db.close()

if __name__ == "__main__":
    seed_demo_environment()
