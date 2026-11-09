"""
Network traffic ingestion and feature extraction.
"""

import logging
from typing import Iterator
from detection.engine import NetworkFlow, ThreatEvent

logger = logging.getLogger("core.ingestion")

def simulate_ingestion() -> Iterator[NetworkFlow]:
    """Simulate network flow ingestion for demo."""
    import time
    import random
    flow_id = 0
    while True:
        flow = NetworkFlow(
            protocol=random.randint(6, 17),
            src_port=random.randint(1, 65535),
            dst_port=random.randint(1, 65535),
            pkt_count=random.randint(1, 1000),
            byte_count=random.randint(100, 100000),
            duration=random.uniform(1, 300),
            pkt_size_mean=random.uniform(50, 1500),
            pkt_size_std=random.uniform(10, 500),
            inter_arrival_mean=random.uniform(0.1, 5.0),
            tcp_flags=random.randint(0, 31),
            is_bidirectional=random.choice([0, 1]),
        )
        yield flow
        flow_id += 1
        time.sleep(random.uniform(0.1, 2.0))

def flows_to_threats(flows: Iterator[NetworkFlow], detector) -> Iterator[ThreatEvent]:
    """Convert flows to threat events."""
    for flow in flows:
        features = flow.to_feature_vector()
        threat = detector.detect(features, "10.0.0.1", "192.168.1.1", time.time())
        if threat:
            yield threat


if __name__ == "__main__":
    logger.info("Ingestion demo ready")

