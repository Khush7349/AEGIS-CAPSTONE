"""
Base agent class with Redis Pub/Sub communication.
"""

import logging
import json
import threading
import time
from typing import Dict, Any, Optional, Callable
import redis

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")

class Channels:
    THREATS = "aegis:threats"
    DASHBOARD = "aegis:dashboard"
    DECEPTION = "aegis:deception"
    RESPONSE = "aegis:response"
    HUMAN_APPROVE = "aegis:human:approve"
    HUMAN_QUEUE = "aegis:human:queue"


class BaseAgent:
    def __init__(self, name: str, redis_host: str = "localhost", redis_port: int = 6379):
        self.name = name
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, decode_responses=True)
        self.running = False
        self.subscriptions: Dict[str, Callable] = {}
        self.thread = None
        self.logger = logging.getLogger(f"agents.{name}")
    
    def subscribe(self, channel: str, callback: Callable):
        """Subscribe to Redis channel."""
        self.subscriptions[channel] = callback
        self.logger.info(f"Subscribed to {channel}")
    
    def publish(self, channel: str, message: Dict[str, Any]):
        """Publish message to Redis channel."""
        self.redis_client.publish(channel, json.dumps(message))
        self.logger.debug(f"Published to {channel}: {message}")
    
    def set_state(self, state: Dict[str, Any]):
        """Set agent state."""
        self.redis_client.set(f"{self.name}:state", json.dumps(state))
    
    def get_state(self, key: str) -> Optional[Dict[str, Any]]:
        """Get agent state."""
        data = self.redis_client.get(key)
        return json.loads(data) if data else None
    
    def _run_loop(self):
        """Main agent loop."""
        pubsub = self.redis_client.pubsub()
        for channel in self.subscriptions:
            pubsub.subscribe(channel)
        
        self.logger.info("Agent loop started")
        while self.running:
            message = pubsub.get_message(timeout=1.0)
            if message and message['type'] == 'message':
                try:
                    data = json.loads(message['data'])
                    callback = self.subscriptions.get(message['channel'])
                    if callback:
                        callback(data)
                except Exception as e:
                    self.logger.error(f"Message error: {e}")
        pubsub.close()
    
    def start(self):
        """Start agent."""
        self.running = True
        self.thread = threading.Thread(target=self._run_loop, daemon=True)
        self.thread.start()
        self.set_state({"status": "running", "timestamp": time.time()})
        self.logger.info("Agent started")
    
    def stop(self):
        """Stop agent."""
        self.running = False
        self.set_state({"status": "stopped", "timestamp": time.time()})
        self.logger.info("Agent stopped")


if __name__ == "__main__":
    agent = BaseAgent("test")
    agent.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        agent.stop()

