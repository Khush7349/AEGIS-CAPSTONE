#!/usr/bin/env python3
"""
Initialize RAG knowledge base.
"""

from rag.knowledge_base import ThreatKnowledgeBase, seed_mitre_attack

kb = ThreatKnowledgeBase()
seed_mitre_attack(kb)
kb.save("data/rag")
print("RAG initialized with 7 documents in data/rag/")

