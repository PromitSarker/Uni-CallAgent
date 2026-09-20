import sys
sys.path.append('.')
from agent.rag import add_document

usp_text = """
Low-Latency, High-Performance Network
Performance is measured, not assumed:
• ~50+ms latency to AWS
• 1–3ms latency on our unified network

Network security is monitored and defended by our in-house Security Operations Center (SOC), giving us direct oversight of threats rather than relying on third parties.

Private Network Connectivity — Independent of the Public Internet
Our private network is engineered to function even when the public internet isn't available.
Through direct connections to ALL telecom carriers, 50+ ISP services, BDIX, and NIX, services hosted within our unified network remain reachable to end users independent of standard internet access.

This isn't theoretical — it's proven.
During the 2024 nationwide internet shutdown, our infrastructure kept internet services running for our clients without interruption.
We are connected with 50+ ISP services and ALL telecom operators, reinforcing this level of network resilience and reach. Note: It is 50+ ISP services, but ALL telecom operators (do not confuse the two).

These are our Unique Selling Propositions (USPs).
"""

doc_id = add_document(usp_text, {"title": "Unique Selling Propositions (USPs)"})
print(f"Added USP document with ID: {doc_id}")
