#!/usr/bin/env python3
"""
AEGIS demo orchestrator.
"""

import logging
import threading
import time
import sys
import signal
from typing import List

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("run_demo")

# Placeholder agents (full impl in next steps)
class DummyAgent:
    def __init__(self, name):
        self.name = name
    
    def run(self):
        logger.info(f"{self.name} running...")
        while True:
            time.sleep(1)

def main():
    agents = [DummyAgent("Detection"), DummyAgent("Reasoning"), DummyAgent("Deception"), DummyAgent("Response")]
    threads = []

    def signal_handler(sig, frame):
        logger.info("Shutting down...")
        sys.exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)

    for agent in agents:
        t = threading.Thread(target=agent.run, daemon=True)
        t.start()
        threads.append(t)
    
    logger.info("All agents started. Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()

