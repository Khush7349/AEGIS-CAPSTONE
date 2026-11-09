"""
RAG knowledge base with FAISS indexing and MITRE ATT&CK/CVE seeding.
"""

import logging
import os
import json
from dataclasses import dataclass
from typing import List, Optional

import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import TfidfVectorizer

try:
    import faiss
except ImportError:
    faiss = None

logger = logging.getLogger("rag.knowledge_base")


@dataclass
class ThreatDocument:
    doc_id: str
    title: str
    content: str
    threat_type: str
    source: str
    embedding: Optional[np.ndarray] = None


class ThreatKnowledgeBase:
    def __init__(self):
        self.documents: List[ThreatDocument] = []
        self.embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        self.index = faiss.IndexFlatIP(384) if faiss else None
    
    def add_document(self, doc: ThreatDocument):
        emb = self.embedding_model.encode([doc.content])[0]
        doc.embedding = emb
        self.documents.append(doc)
        if self.index:
            self.index.add(emb.reshape(1, -1).astype('float32'))
    
    def retrieve(self, query: str, k: int = 3) -> List[ThreatDocument]:
        if not self.documents:
            return []
        query_emb = self.embedding_model.encode([query])[0]
        if self.index:
            scores, indices = self.index.search(query_emb.reshape(1, -1).astype('float32'), k)
            return [self.documents[i] for i in indices[0] if i < len(self.documents)]
        return self.documents[:k]
    
    def save(self, path: str):
        os.makedirs(path, exist_ok=True)
        docs = [{'doc_id': d.doc_id, 'title': d.title, 'content': d.content, 'threat_type': d.threat_type, 'source': d.source} for d in self.documents]
        with open(os.path.join(path, 'faiss_index.json'), 'w') as f:
            json.dump(docs, f)
    
    def load(self, path: str):
        json_path = os.path.join(path, 'faiss_index.json')
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                docs_data = json.load(f)
            for data in docs_data:
                doc = ThreatDocument(**data)
                emb = self.embedding_model.encode([doc.content])[0]
                doc.embedding = emb
                self.documents.append(doc)
                if self.index:
                    self.index.add(emb.reshape(1, -1).astype('float32'))


def seed_mitre_attack(kb: ThreatKnowledgeBase):
    docs = [
        ThreatDocument("T1046", "Network Service Scanning", "Port scanning: high pkt_count varied ports short duration", "PORTSCAN", "mitre"),
        ThreatDocument("T1498", "Network Denial of Service", "DDoS: massive pkt/byte count short duration", "DDOS", "mitre"),
        ThreatDocument("T1021", "Remote Services", "Lateral movement: bidirectional moderate pkts", "LATERAL", "mitre"),
        ThreatDocument("T1048", "Exfiltration", "High bytes long duration bidirectional", "EXFIL", "mitre"),
        ThreatDocument("T1190", "Exploit Public Apps", "Unusual pkt sizes/flags", "EXPLOIT", "mitre"),
        ThreatDocument("T1071", "C2 Channels", "Regular beaconing bidirectional", "C2", "mitre"),
        ThreatDocument("PLAYBOOK", "Honeypot Playbook", "Redirect to decoy ports log fingerprint escalate >0.7", "DECEPTION", "playbook"),
    ]
    for doc in docs:
        kb.add_document(doc)
    logger.info(f"Seeded {len(docs)} MITRE documents")


if __name__ == "__main__":
    kb = ThreatKnowledgeBase()
    seed_mitre_attack(kb)
    kb.save("data")

