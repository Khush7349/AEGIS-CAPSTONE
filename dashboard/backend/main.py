"""
AEGIS Dashboard Backend: FastAPI server with WebSocket streaming.
"""

import logging
import json
from datetime import datetime, timedelta
from typing import List, Dict, Any

from fastapi import FastAPI, WebSocket, Query, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import redis
import redis.asyncio as aioredis
import asyncio
from collections import defaultdict

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)

logger = logging.getLogger("dashboard.backend")

app = FastAPI(title="AEGIS Dashboard API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis
redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True, socket_timeout=5)

class ApprovalRequest(BaseModel):
    action_id: str
    approved: bool
    comments: str = ""

connected_clients: List[WebSocket] = []

@app.get("/api/health")
async def health_check():
    try:
        redis_client.ping()
        return {"status": "operational", "timestamp": datetime.utcnow().isoformat()}
    except:
        return {"status": "degraded", "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/alerts")
async def get_alerts(limit: int = 100, severity_min: float = 0.0):
    alerts = []
    for key in redis_client.keys("threat:*")[-limit*2:]:
        data = redis_client.get(key)
        if data:
            try:
                alert = json.loads(data)
                if alert.get("severity", 0) >= severity_min:
                    alerts.append(alert)
            except:
                pass
    alerts.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
    return {"alerts": alerts[:limit]}

@app.get("/api/stats")
async def get_stats():
    threat_counts = defaultdict(int)
    for key in redis_client.keys("threat:*"):
        data = redis_client.get(key)
        if data:
            try:
                threat_type = json.loads(data).get("threat_type", "UNKNOWN")
                threat_counts[threat_type] += 1
            except:
                pass
    return {"threat_counts": dict(threat_counts), "timestamp": datetime.utcnow().isoformat()}

@app.get("/api/threats/timeline")
async def get_threats_timeline(hours: int = 24):
    timeline = {}
    now = datetime.utcnow()
    for i in range(hours):
        timeline[(now - timedelta(hours=i)).isoformat()[:13]] = 0
    for key in redis_client.keys("threat:*"):
        data = redis_client.get(key)
        if data:
            try:
                ts = datetime.fromisoformat(json.loads(data).get("timestamp"))
                hour = ts.isoformat()[:13]
                timeline[hour] = timeline.get(hour, 0) + 1
            except:
                pass
    return {"timeline": timeline}

@app.get("/api/pending-actions")
async def get_pending_actions():
    pending = []
    for key in redis_client.keys("pending-action:*"):
        data = redis_client.get(key)
        if data:
            pending.append(json.loads(data))
    return {"pending_actions": pending}

@app.post("/api/approve-action")
async def approve_action(request: ApprovalRequest):
    redis_client.publish("aegis:human:approve", json.dumps(request.dict()))
    return {"status": "approved"}

@app.post("/api/generate-report")
async def generate_report():
    alerts = []
    for key in redis_client.keys("threat:*")[-10:]:
        data = redis_client.get(key)
        if data:
            alerts.append(json.loads(data))
    report = {
        "format": "SALUTE",
        "timestamp": datetime.utcnow().isoformat(),
        "threats": len(alerts),
        "alerts": alerts
    }
    return report

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        r = await aioredis.from_url("redis://localhost:6379")
        pubsub = r.pubsub()
        await pubsub.subscribe("aegis:dashboard")
        async for message in pubsub.listen():
            if message["type"] == "message":
                await websocket.send_text(message["data"])
    except:
        pass
    finally:
        connected_clients.remove(websocket)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

