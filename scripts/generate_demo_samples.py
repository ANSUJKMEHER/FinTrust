"""
FinTrust RAG — Demo Document Generator
Generates realistic financial reports and regulatory compliance documents
in PDF, DOCX, and Markdown formats for live demonstration.
"""

import os
from pathlib import Path
import fitz  # PyMuPDF
from docx import Document

OUTPUT_DIR = Path("demo_samples")
OUTPUT_DIR.mkdir(exist_ok=True)

def generate_pdf():
    pdf_path = OUTPUT_DIR / "Apex_Financial_Holdings_Q3_2026_Earnings.pdf"
    doc = fitz.open()

    # Page 1: Financial Highlights & Overview
    page1 = doc.new_page()
    text1 = """APEX FINANCIAL HOLDINGS, INC.
FORM 10-Q QUARTERLY FINANCIAL PERFORMANCE & RISK REPORT
THIRD QUARTER 2026 (PERIOD ENDED SEPTEMBER 30, 2026)

1. EXECUTIVE FINANCIAL HIGHLIGHTS
Apex Financial Holdings reported third-quarter net income of $4.25 Billion ($3.42 per diluted share),
compared to $3.80 Billion ($3.05 per diluted share) in the prior-year period. Total net revenue on a
managed basis was $15.40 Billion, representing an 8.6% year-over-year expansion driven by robust
commercial banking performance and asset management fees.

- Net Interest Income (NII): $9.15 Billion, up 5.4% YoY.
- Non-Interest Revenue: $6.25 Billion, driven by investment banking and advisory fees of $1.85 Billion.
- Return on Tangible Common Equity (ROTCE): 20.4%, compared with 18.2% in Q3 2025.
- Efficiency Ratio: 52.8%, down from 54.1% in the prior quarter.

2. CAPITAL ADEQUACY & REGULATORY RATIOS
The Firm maintained fortress balance sheet principles, with regulatory capital ratios substantially
exceeding all Basel III and Federal Reserve minimum requirements:

- Common Equity Tier 1 (CET1) Capital Ratio: 15.3% (standardized approach), representing an excess
  capital buffer of $42.5 Billion over regulatory minimums.
- Tier 1 Risk-Based Capital Ratio: 17.1%.
- Total Capital Ratio: 19.4%.
- Liquidity Coverage Ratio (LCR): 146%, well above the 100% regulatory baseline.
- Supplementary Leverage Ratio (SLR): 6.1%.
"""
    page1.insert_text((50, 50), text1, fontsize=10, lineheight=1.3)

    # Page 2: Risk Management & Credit Loss
    page2 = doc.new_page()
    text2 = """APEX FINANCIAL HOLDINGS, INC. — Q3 2026 RISK REPORT (CONTINUED)

3. CREDIT RISK & ALLOWANCE FOR CREDIT LOSSES
The Provision for Credit Losses was $720 Million for the quarter, compared to $650 Million in Q2 2026.
Total Allowance for Credit Losses (ACL) reached $14.2 Billion, providing 2.35x coverage of
non-performing loans.

- Non-Performing Loan (NPL) Ratio: 0.44% of total customer loans, reflecting stable asset quality.
- Net Charge-Offs (NCOs): $480 Million annualized rate of 0.38%.
- Commercial Real Estate (CRE) Exposure: Reduced to 8.2% of total loan book, with office exposure
  specifically stressed and weighted with an average loan-to-value (LTV) ratio of 58%.

4. SEVERE ADVERSE STRESS TEST SCENARIO
Under the internal Dodd-Frank Act Stress Testing (DFAST) adverse scenario modeled against a 4.5% drop
in real GDP, a peak unemployment rate of 9.5%, and a 30% drop in commercial property values:
- Firm projected minimum CET1 ratio trough: 11.2% (comfortably above the 4.5% statutory threshold).
- Cumulative 9-quarter projected pre-provision net revenue: $32.4 Billion.
"""
    page2.insert_text((50, 50), text2, fontsize=10, lineheight=1.3)

    doc.save(str(pdf_path))
    doc.close()
    print(f"Generated PDF: {pdf_path}")


def generate_docx():
    docx_path = OUTPUT_DIR / "Global_Banking_Anti_Money_Laundering_Policy_2026.docx"
    doc = Document()

    doc.add_heading("GLOBAL BANKING CORPORATION", level=0)
    doc.add_heading("Enterprise Anti-Money Laundering (AML) & Sanctions Compliance Policy", level=1)
    doc.add_paragraph("Policy Version: 2026.4 | Effective Date: October 1, 2026 | Approved by Board Risk Committee")

    doc.add_heading("Section 1: Beneficial Ownership Verification Standards", level=2)
    doc.add_paragraph(
        "Under FinCEN Customer Due Diligence (CDD) requirements (31 CFR § 1010.230), covered institutions "
        "must identify and verify the identity of the beneficial owners of all legal entity customers opening an account."
    )
    doc.add_paragraph(
        "Standard Ownership Threshold: Any individual who, directly or indirectly, through any contract, arrangement, "
        "understanding, relationship or otherwise, owns 25 percent or more of the equity interests of a legal entity."
    )
    doc.add_paragraph(
        "High-Risk Customer Threshold: For entities operating in high-risk sectors (e.g., private investment companies, "
        "casinos, money services businesses) or foreign jurisdictions identified on the FATF Grey List, the Firm applies "
        "an enhanced threshold of 10 percent or more equity ownership."
    )

    doc.add_heading("Section 2: Enhanced Due Diligence (EDD) Mandatory Triggers", level=2)
    doc.add_paragraph(
        "Enhanced Due Diligence (EDD) must be conducted and formally approved by the Chief Compliance Officer (CCO) "
        "prior to establishing a business relationship under any of the following mandatory conditions:"
    )
    doc.add_paragraph("1. Politically Exposed Persons (PEPs): Any customer or beneficial owner designated as a PEP, immediate family member, or close associate.")
    doc.add_paragraph("2. Sanctions Boundary Accounts: Cross-border wires exceeding $50,000 involving jurisdictions subject to OFAC targeted sanctions.")
    doc.add_paragraph("3. Shell Banking Restrictions: Strict prohibition from establishing or maintaining correspondent accounts for foreign shell banks.")

    doc.add_heading("Section 3: Record Retention & Travel Rule Protocols", level=2)
    doc.add_paragraph(
        "Funds Transfer Travel Rule (31 CFR § 1010.410(e)): For all funds transfers of $3,000 or more, the transmittal order "
        "must include the originator's name, account number, physical address, recipient's name, and execution timestamp."
    )
    doc.add_paragraph(
        "Statutory Record Retention: All AML customer identification records, SAR filings, and supporting workpapers "
        "must be retained for a mandatory minimum period of seven (7) years following account termination."
    )

    doc.save(str(docx_path))
    print(f"Generated DOCX: {docx_path}")


def generate_markdown():
    md_path = OUTPUT_DIR / "Silicon_Valley_Fintech_Risk_Disclosure_2026.md"
    content = """# Silicon Valley Digital Financial, Inc. (FinTech)
## Comprehensive Risk Assessment & AI Governance Disclosure 2026

### 1. Market & Capital Risk Analysis
Silicon Valley Digital Financial operates a decentralized consumer credit and automated algorithmic lending platform.
- **Total Loan Portfolio Originations**: $2.85 Billion across 340,000 active retail accounts.
- **Effective Annual Percentage Rate (APR) Range**: 7.2% to 24.5%, with a weighted average loan term of 36 months.
- **Liquidity Facility Reserve**: Backed by a $600 Million revolving credit facility from a Tier 1 syndicate.
- **Default Probability Modeling**: Expected credit loss (ECL) under CECL methodology estimated at 3.12% ($88.9 Million).

### 2. Responsible AI & Model Governance Framework
All algorithmic credit underwriting decisions are governed by the Firm's Model Risk Management (MRM) Policy:
- **Bias & Disparate Impact Auditing**: Automated algorithms are audited quarterly under the Equal Credit Opportunity Act (ECOA / Regulation B) to prevent disparate impact on protected demographic classes.
- **Model Explainability**: Every rejected applicant receives an automated adverse action notice citing the top 4 adverse factors (e.g., debt-to-income ratio, revolving credit utilization) within 30 days.
- **Human-in-the-Loop Override**: Credit line recommendations exceeding $75,000 cannot be executed autonomously and require dual authorization from Senior Underwriting and Compliance.

### 3. Cybersecurity & Data Privacy Posture
- **Encryption Standards**: All customer non-public personal information (NPI) is encrypted at rest using AES-256-GCM and in transit using TLS 1.3.
- **Zero-Trust Access**: Administrative database access mandates hardware token FIDO2/WebAuthn multi-factor authentication.
- **SOC 2 Type II Certification**: Completed with zero material exceptions reported by independent auditors.
"""
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Generated Markdown: {md_path}")

if __name__ == "__main__":
    generate_pdf()
    generate_docx()
    generate_markdown()
    print("\nAll demo sample files generated successfully!")
