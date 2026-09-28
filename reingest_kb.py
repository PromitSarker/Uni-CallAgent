"""
Re-ingest RAG Knowledge Base — Clears existing data and re-uploads with proper chunking.

Run this script INSIDE the Docker container or locally with the venv active:
    python reingest_kb.py
"""
import sys
sys.path.append('.')

from agent.rag import _vectorstore, add_document, list_documents

# Step 1: Clear all existing documents
print("=" * 60)
print("Step 1: Clearing existing ChromaDB documents...")
print("=" * 60)

existing = list_documents()
print(f"Found {len(existing)} existing documents/chunks.")

if existing:
    for doc in existing:
        try:
            _vectorstore.delete(ids=[doc["id"]])
        except Exception as e:
            print(f"  Warning: Could not delete {doc['id']}: {e}")
    print(f"Deleted {len(existing)} documents.")
else:
    print("No existing documents to delete.")

# Verify deletion
remaining = list_documents()
print(f"Remaining docs after cleanup: {len(remaining)}")

# Step 2: Re-upload the knowledge base as separate sections
print("\n" + "=" * 60)
print("Step 2: Re-ingesting knowledge base with proper chunking...")
print("=" * 60)

# Each section is uploaded separately with clear metadata
sections = [
    {
        "title": "Company Overview & Administrative Information",
        "text": """Company Overview & Administrative Information
Full Company Name: Unified Information Technology Limited (UITL)
Tagline: "Your Own Cloud"
Corporate Office Address: Mannan Tower (3rd Floor), Ka 96/3 Progati Sharani, Dhaka 1229, Bangladesh.
Direct Contact Number: 09617-200800
WhatsApp Contact: +880 1712-814233
MFS (Bkash & Nagad): +880 1712-814233
Email Contact: info@unified.it.com
Sales Email (For Uncovered Queries): sales@unified.it.com
Official Website: web.unified.it.com
Registration & Signup: Clients can visit web.unified.it.com to sign up and instantly access Unified Cloud services through a fully automated platform.
Target Industry Sectors: Garments/RMG, Banking & Financial Institutions, Healthcare, Retail, E-Commerce, and Large Enterprise Sectors requiring ultra-low latency and zero downtime."""
    },
    {
        "title": "Core Infrastructure & High Availability Architecture",
        "text": """Core Infrastructure & High Availability Architecture
Multi-Site Distributed Data Center Footprint:
Dhaka Active-Active Cluster: Features three (3) active-active Data Centers located in Mohakhali, Gulshan-1, and Gulshan-2.
Regional Footprint (DR & Cold Storage): Extended data center footprint to Jessore and Kaliakair for Disaster Recovery (DR) and long-term Cold Storage.
No Single Point of Failure (SPOF): Deliberate geological and geographic separation protects workloads from natural disasters, physical disruptions, or localized power outages.
Zero-Downtime Architecture:
Isolated Compute & Storage Layers: Across all active-active facilities, compute resources and storage resources operate as independently isolated layers.
Storage-Compute Decoupling: Storage is kept strictly separate from compute. Issues affecting compute resources do not impact storage integrity, and vice versa.
Dedicated Backup Infrastructure: Each layer possesses its own dedicated backup infrastructure. Workloads shift seamlessly across nodes without service interruption or human intervention in case of a hardware/node failure."""
    },
    {
        "title": "Ultra-Low Latency & Network Performance",
        "text": """Ultra-Low Latency & Resilient Network Architecture
Performance Benchmarks:
Local Unified Cloud Latency: 1 ms to 3 ms ping response within Bangladesh.
Global Cloud Benchmark: 50 ms to 60 ms ping response to nearest regional hubs (in Singapore).
Speed Advantage: Delivers up to 23x faster performance for Dhaka users compared to the nearest global cloud region.
Private Network Connectivity & Sovereignty:
Virtual DMZ (Isolated Private Networks): Allows clients to build completely secure private networks with internal IP addressing for application and database tiers. Public services are exposed via reverse proxy port forwarding.
Direct Fiber Connections: Direct fiber optic links to client premises via partnerships with over 50 local ISPs—completely removing the requirement for public internet to access private workloads.
National Internet Exchange Backhaul: Direct backhaul links to NIX, BDIX, and all major telco operators (Grameenphone, Robi, Banglalink, Teletalk, Cirkle).
Proven Internet Shutdown Resilience: Designed to run continuously even during international submarine cable cuts or total nationwide internet blackouts (proven during the 2024 Bangladesh internet shutdown).
SIM-Based Private Connectivity: Supports router-installed SIM cards via telco partnerships to run software or connect remote branch locations securely through private networks without public internet."""
    },
    {
        "title": "Security Operations Center & Firewall Architecture",
        "text": """Security Operations Center (SOC) & Next-Gen Firewalls
In-House SOC: Monitored and defended 24/7 by an internal Security Operations Center providing direct oversight of cyber threats without relying on third parties.
Enterprise Firewall Architecture: Utilizes Gartner-recognized Next-Generation Firewalls (NGFW) with AI-powered threat detection, real-time blocking, SSL inspection/decryption, Intrusion Prevention System (IPS), URL filtering, and application control."""
    },
    {
        "title": "ISO Certifications & Compliance Standards",
        "text": """ISO Certifications & Compliance Standards
ISO 27001:2022 (Information Security Management System - ISMS):
Certificate No: INQ/AN-25464/129481/1225
Validity: Registered/Issued 02-12-2025 | Expires 01-12-2028
Scope: DATA security

ISO 22301:2019 (Business Continuity Management System - BCMS):
Certificate No: INQ/AN-25539/129491/1225
Validity: Registered/Issued 03-12-2025 | Expires 02-12-2028
Scope: Guarantees business continuity, multi-data-center redundancy, service protection, and disaster recovery execution.

PCI DSS Compliance: Meets requirements for secure payment card processing and financial data storage.
SAP HANA Compliance: Fully compliant and verified to deploy SAP HANA Database workloads.
Oracle AI Database Compliance: Fully compliant and verified to deploy Oracle AI Database.
HIPAA Compliance: Meets privacy, security, and integrity requirements for healthcare organizations protecting Protected Health Information (PHI).
Data Sovereignty & Geofencing: Customer data strictly resides within Bangladesh boundaries, fully adhering to local government data privacy and compliance policies."""
    },
    {
        "title": "Cloud & Infrastructure Services (IaaS, PaaS, SaaS, GPU)",
        "text": """Cloud & Infrastructure Stack
Infrastructure as a Service (IaaS): Public Cloud and Private Cloud with dedicated IP and private IP addressing, customizable virtual infrastructure, and full root access.
Platform as a Service (PaaS): Managed development and deployment environments.
Software as a Service (SaaS): Ready-to-use business application platforms.
GPU as a Service (GPUaaS): High-performance on-demand GPU compute tailored for AI/ML model training, inference workloads, rendering, and complex scientific calculations.
Cloud VPS: Scalable virtual private servers with guaranteed resource allocation.
Dedicated Bare-Metal Servers: Enterprise-grade bare-metal hardware designed for high-traffic databases, ERP systems, and heavy enterprise workloads (computable for SAP, Oracle, Akhil Systems, etc.).
Cloud Storage & Automated Backup: Scalable file and object storage paired with automated disaster recovery systems.
Repository Service: Scalable Private and Public repository service powered by Unified-Git.
Bundled Enterprise Licensing: Windows Virtual Machines come pre-installed with official, integrated Windows Server and SQL Server licenses embedded into instance pricing—eliminating separate licensing headaches."""
    },
    {
        "title": "AI Solutions & Business Automation",
        "text": """AI Solutions & Business Automation
Agentic AI & AI Agents: Task-executing, decision-making AI agents designed for customer support automation, lead generation, and workflow execution.
Process Automation: Task management, auto-notifications, real-time data synchronization, and CRM/third-party integrations."""
    },
    {
        "title": "Unified Communication & Messaging Solutions",
        "text": """Unified Communication & Messaging Solutions
Business Email Services:
Unified business email service.
Official Microsoft 365 partnerships.
Hybrid Mail Services: Seamless integration combining with Microsoft 365 or Google Workspace.

Bulk SMS Services:
Promotional bulk SMS (Masking and Non-Masking options).
Transactional OTP & Verification SMS with instant API delivery and real-time reports.
Shortcode SMS Service.
Toll-Free SMS Service.
Push-Pull SMS Service.

BTRC-Licensed Call Center Solution:
IP PBX Hosting service.
Interactive Voice Response (IVR) & Auto-Response service.
Call Recording & Real-time Call Monitoring service.
Remote Agent Support capabilities."""
    },
    {
        "title": "Web Hosting & Domain Management",
        "text": """Web Hosting & Domain Management
Domain Registration: .com, .bd, and international TLDs with full DNS management and security.
Web Hosting: Shared, VPS, and managed web hosting supporting business websites, corporate portals, and e-commerce platforms.
SSL Certificates: Web security certificates issued by global certificate authorities."""
    },
    {
        "title": "Software Service Partners & Managed Application Ecosystem",
        "text": """Software Service Partners & Managed Application Ecosystem
We offer a one-stop solution by supplying and managing access to software applications through an AI-powered ecosystem of software partners. We do not build or develop the core software applications we provide. Instead, we partner with software providers, supply their applications to users, and manage the surrounding application ecosystem. Where needed, we can develop AI solutions to support or enhance that ecosystem.
We offer :
Accounting Management System
Inventory Management System
HR & Payroll Software (HRIS)
Sales & CRM Systems
Business Reporting & Insights Dashboards
Custom Enterprise Resource Planning (ERP) Solutions
Hospital Information Systems (HIS) & E-Commerce platforms"""
    },
    {
        "title": "Business Growth Framework & Hosting Plans",
        "text": """Business Growth Framework & Hosting Plans
Five-Stage Business Growth Journey:
1. Launch: Start your digital journey (Domain, Web Hosting, Starter Cloud).
2. Communication: Connect & Engage (Business Email, Bulk SMS, Call Center).
3. Automation: Work Smarter, Not Harder (AI Agents, Process Automation).
4. Enterprise Growth: Scale Your Business (Dedicated Servers, Custom ERP, GPUaaS).
5. Security: Protect What Matters (SOC, Managed Backup, ISO Security Audits).

Hosting Tiers:
Starter Plan: Designed for personal websites, portfolios, and small businesses starting out.
Business Plan: Designed for growing businesses requiring increased compute resources and enhanced security.
Professional Plan (Most Popular): Optimized for established companies running multiple sites, e-commerce stores, or SaaS apps.
Enterprise Plan: Fully customizable bare-metal or cloud infrastructure with dedicated resources, priority engineering support, and SLA guarantees."""
    },
    {
        "title": "Managed Operations & Pricing Model",
        "text": """Managed Operations & Pricing Model
End-to-End Managed Services: In-house engineers handle OS maintenance, patch management, automated backups, centralized logging, database optimization, and server migrations with minimal downtime.
Flexible Pricing Model: Pay for active resources and users to optimize operational expenses."""
    },
    {
        "title": "Fallback & Uncovered Query Handling",
        "text": """Fallback & Uncovered Query Handling (AI Agent Directive)
When a customer asks a question or requests information that is not covered by the data in this knowledge base, the AI Agent must respond by directing the client to the Sales team using the following contact channels:
Sales Email: sales@unified.it.com
Direct WhatsApp: +880 1712-814233"""
    },
    {
        "title": "Unique Selling Propositions (USPs)",
        "text": """Unique Selling Propositions (USPs)
Low-Latency, High-Performance Network
Performance is measured, not assumed:
~50+ms latency to AWS
1-3ms latency on our unified network

Network security is monitored and defended by our in-house Security Operations Center (SOC), giving us direct oversight of threats rather than relying on third parties.

Private Network Connectivity — Independent of the Public Internet
Our private network is engineered to function even when the public internet isn't available.
Through direct connections to ALL telecom carriers, 50+ ISP services, BDIX, and NIX, services hosted within our unified network remain reachable to end users independent of standard internet access.

This isn't theoretical — it's proven.
During the 2024 nationwide internet shutdown, our infrastructure kept internet services running for our clients without interruption.
We are connected with 50+ ISP services and ALL telecom operators, reinforcing this level of network resilience and reach. Note: It is 50+ ISP services, but ALL telecom operators (do not confuse the two).

These are our Unique Selling Propositions (USPs)."""
    },
]

total_chunks = 0
for section in sections:
    doc_ids = add_document(section["text"], {"title": section["title"]})
    chunk_count = len(doc_ids)
    total_chunks += chunk_count
    print(f"  [{chunk_count} chunks] {section['title']}")

# Step 3: Verify
print("\n" + "=" * 60)
print("Step 3: Verification")
print("=" * 60)
final_docs = list_documents()
print(f"Total chunks in ChromaDB: {len(final_docs)}")
print(f"Expected chunks from ingestion: {total_chunks}")

# Quick test
print("\n" + "=" * 60)
print("Step 4: Quick search test — 'SAP HANA compliance'")
print("=" * 60)
from agent.rag import search_documents
result = search_documents("SAP HANA compliance", k=3)
print(result[:500])
print("\nDone! Re-ingestion complete.")
