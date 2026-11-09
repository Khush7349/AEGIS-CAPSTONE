"""
Anomaly detection engine combining Isolation Forest and LSTM Autoencoder.
"""

import logging
import pickle
import os
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict, Any
from collections import deque
import json

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

logger = logging.getLogger("detection.engine")


@dataclass
class NetworkFlow:
    """Network flow representation with feature extraction."""
    
    protocol: int
    src_port: int
    dst_port: int
    pkt_count: int
    byte_count: int
    duration: float  # seconds
    pkt_size_mean: float
    pkt_size_std: float
    inter_arrival_mean: float
    tcp_flags: int
    is_bidirectional: int  # 0 or 1
    
    def to_feature_vector(self) -> List[float]:
        """Extract 11-feature vector for ML models."""
        return [
            self.protocol,
            self.src_port,
            self.dst_port,
            self.pkt_count,
            self.byte_count,
            self.duration,
            self.pkt_size_mean,
            self.pkt_size_std,
            self.inter_arrival_mean,
            self.tcp_flags,
            self.is_bidirectional,
        ]


@dataclass
class ThreatEvent:
    """Detected threat event."""
    
    timestamp: float
    src_ip: str
    dst_ip: str
    threat_type: str
    severity: float
    confidence: float
    feature_vector: List[float]
    detection_method: str
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class IsolationForestDetector:
    def __init__(self, contamination: float = 0.1):
        self.if_model = IsolationForest(contamination=contamination, random_state=42, n_estimators=100)
        self.scaler = StandardScaler()
        self.is_fitted = False
    
    def fit(self, X: np.ndarray):
        logger.info(f"Fitting IsolationForest on {X.shape[0]} samples")
        X_scaled = self.scaler.fit_transform(X)
        self.if_model.fit(X_scaled)
        self.is_fitted = True
    
    def score(self, X: np.ndarray) -> np.ndarray:
        if not self.is_fitted:
            return np.zeros(len(X))
        X_scaled = self.scaler.transform(X)
        scores = -self.if_model.score_samples(X_scaled)
        return np.clip(scores, 0, 1)
    
    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            pickle.dump({"if_model": self.if_model, "scaler": self.scaler}, f)
    
    def load(self, path: str):
        if os.path.exists(path):
            with open(path, "rb") as f:
                data = pickle.load(f)
                self.if_model = data["if_model"]
                self.scaler = data["scaler"]
                self.is_fitted = True


class LSTMAutoencoder(nn.Module):
    def __init__(self, input_dim: int = 11, hidden_dim: int = 32, num_layers: int = 2):
        super().__init__()
        self.encoder = nn.LSTM(input_dim, hidden_dim, num_layers, batch_first=True, dropout=0.2)
        self.decoder = nn.LSTM(hidden_dim, hidden_dim, num_layers, batch_first=True, dropout=0.2)
        self.linear = nn.Linear(hidden_dim, input_dim)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, (h_n, c_n) = self.encoder(x)
        decoder_input = h_n[-1].unsqueeze(1)
        seq_len = x.shape[1]
        decoded = []
        for _ in range(seq_len):
            out, (h_n, c_n) = self.decoder(decoder_input, (h_n, c_n))
            decoded.append(self.linear(out))
            decoder_input = out
        return torch.cat(decoded, dim=1)
    
    def reconstruction_error(self, x: torch.Tensor) -> torch.Tensor:
        x_hat = self(x)
        error = torch.mean((x - x_hat) ** 2, dim=2)
        return error.mean(dim=1)


class LSTMAEDetector:
    def __init__(self, input_dim: int = 11, seq_len: int = 5, device: str = "cpu"):
        self.input_dim = input_dim
        self.seq_len = seq_len
        self.device = device
        self.model = LSTMAutoencoder().to(device)
        self.scaler = StandardScaler()
        self.is_fitted = False
        self.feature_buffer = deque(maxlen=seq_len)
        self.threshold = 0.5
    
    def fit(self, X: np.ndarray, epochs: int = 20, batch_size: int = 32):
        X_scaled = self.scaler.fit_transform(X)
        sequences = np.array([X_scaled[i:i+self.seq_len] for i in range(len(X_scaled) - self.seq_len + 1)])
        optimizer = optim.Adam(self.model.parameters(), lr=0.001)
        criterion = nn.MSELoss()
        for epoch in range(epochs):
            for i in range(0, len(sequences), batch_size):
                batch = torch.FloatTensor(sequences[i:i+batch_size]).to(self.device)
                x_hat = self.model(batch)
                loss = criterion(batch, x_hat)
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()
        self.is_fitted = True
    
    def score(self, features: np.ndarray) -> float:
        if not self.is_fitted or len(self.feature_buffer) < self.seq_len:
            self.feature_buffer.append(features)
            return 0.0
        buffer_array = np.array(list(self.feature_buffer))
        buffer_scaled = self.scaler.transform(buffer_array)
        batch = torch.FloatTensor(buffer_scaled).unsqueeze(0).to(self.device)
        with torch.no_grad():
            error = self.model.reconstruction_error(batch).item()
        return min(error / self.threshold, 1.0)
    
    def save(self, path: str):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        torch.save({"model_state": self.model.state_dict(), "scaler": self.scaler}, path)
    
    def load(self, path: str):
        if os.path.exists(path):
            checkpoint = torch.load(path, map_location=self.device)
            self.model.load_state_dict(checkpoint["model_state"])
            self.scaler = checkpoint["scaler"]
            self.is_fitted = True


def classify_threat_type(features: List[float], score: float) -> Tuple[str, float]:
    protocol, src_port, dst_port, pkt_count, byte_count, duration, pkt_size_mean, pkt_size_std, inter_arrival_mean, tcp_flags, is_bidirectional = features
    if score < 0.3:
        return "NORMAL", 0.0
    severity = score
    if pkt_count > 50 and duration < 60:
        return "PORTSCAN", min(score, 0.8)
    if pkt_count > 500 or (byte_count > 100000 and duration < 30):
        return "DDOS", min(score, 0.95)
    if is_bidirectional and pkt_count > 20 and tcp_flags > 0:
        return "LATERAL", min(score, 0.7)
    if byte_count > 50000 and duration > 60 and is_bidirectional:
        return "EXFIL", min(score, 0.75)
    if pkt_size_std > pkt_size_mean * 2 or tcp_flags > 10:
        return "EXPLOIT", min(score, 0.8)
    return "ANOMALY", severity


class EnsembleDetector:
    def __init__(self, if_weight: float = 0.5, lstm_weight: float = 0.5, device: str = "cpu"):
        self.if_weight = if_weight
        self.lstm_weight = lstm_weight
        self.device = device
        self.if_detector = IsolationForestDetector()
        self.lstm_detector = LSTMAEDetector(device=device)
    
    def load_or_train(self, model_dir: str = "models", training_data: np.ndarray = None, epochs: int = 10):
        self.if_detector.load(os.path.join(model_dir, "isolation_forest.pkl"))
        self.lstm_detector.load(os.path.join(model_dir, "lstm_ae.pt"))
        if training_data is not None and not self.if_detector.is_fitted:
            self.if_detector.fit(training_data)
            self.lstm_detector.fit(training_data, epochs=epochs)
            self.if_detector.save(os.path.join(model_dir, "isolation_forest.pkl"))
            self.lstm_detector.save(os.path.join(model_dir, "lstm_ae.pt"))
    
    def detect(self, feature_vector: List[float], src_ip: str, dst_ip: str, timestamp: float) -> Optional[ThreatEvent]:
        X = np.array([feature_vector])
        if_score = self.if_detector.score(X)[0] if self.if_detector.is_fitted else 0.0
        lstm_score = self.lstm_detector.score(np.array(feature_vector))
        ensemble_score = self.if_weight * if_score + self.lstm_weight * lstm_score
        if ensemble_score > 0.5:
            threat_type, severity = classify_threat_type(feature_vector, ensemble_score)
            if threat_type != "NORMAL":
                return ThreatEvent(
                    timestamp=timestamp,
                    src_ip=src_ip,
                    dst_ip=dst_ip,
                    threat_type=threat_type,
                    severity=severity,
                    confidence=ensemble_score,
                    feature_vector=feature_vector,
                    detection_method="ensemble"
                )
        return None

