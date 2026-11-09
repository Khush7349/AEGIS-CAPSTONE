"""
Train all AEGIS models and init RAG.
"""

import logging
import os
import numpy as np

from detection.engine import EnsembleDetector
from detection.cgan import CGANTrainer, TabularDiffusion
from rag.knowledge_base import ThreatKnowledgeBase, seed_mitre_attack

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger("train_models")

os.makedirs("models", exist_ok=True)
os.makedirs("data/synthetic", exist_ok=True)
os.makedirs("data/rag", exist_ok=True)

def generate_synthetic_data(n_samples=5000):
    """Generate normal and attack data."""
    normal = np.random.randn(int(n_samples * 0.8), 11) * 0.5 + 0.5
    attack_types = ["PORTSCAN", "DDOS", "LATERAL", "EXFIL", "EXPLOIT"]
    attacks = []
    labels = []
    n_attack = int(n_samples * 0.2 / len(attack_types))
    for i, t in enumerate(attack_types):
        data = np.random.randn(n_attack, 11) * 0.3 + [i*0.1]*11
        attacks.append(data)
        labels.extend([i] * n_attack)
    attacks = np.vstack(attacks)
    return normal, attacks, np.array(labels)

logger.info("1. Training Ensemble Detector")
ensemble = EnsembleDetector()
X_normal, X_attacks, y_attacks = generate_synthetic_data()
X_all = np.vstack([X_normal, X_attacks])
ensemble.load_or_train("models", X_all)

logger.info("2. Training CGAN")
cgan = CGANTrainer()
cgan.train(X_attacks, y_attacks)
cgan.save(os.path.join("models", "cgan.pt"))
synthetic = cgan.generate(500, np.random.randint(0, 6, 500))
np.save("data/synthetic/cgan_features.npy", synthetic)

logger.info("3. Training Diffusion")
diffusion = TabularDiffusion()
diffusion.train(X_attacks)
diffusion_samples = diffusion.sample(500)
np.save("data/synthetic/diffusion_samples.npy", diffusion_samples)

logger.info("4. Init RAG")
kb = ThreatKnowledgeBase()
seed_mitre_attack(kb)
kb.save("data/rag")

logger.info("✓ ALL MODELS TRAINED! Check models/ and data/")

