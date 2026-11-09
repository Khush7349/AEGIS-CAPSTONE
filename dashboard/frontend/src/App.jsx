import React, { useState, useEffect, useRef, useCallback } from 'react';
import './App.css';

const App = () => {
  const [alerts, setAlerts] = useState([]);
  const [stats, setStats] = useState({});
  const [pendingActions, setPendingActions] = useState([]);
  const [wsConnected, setWsConnected] = useState(false);
  const [attackerIps, setAttackerIps] = useState([]);
  const wsRef = useRef(null);
  const alertsRef = useRef(null);

  // WebSocket
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8000/ws');
    wsRef.current = ws;

    ws.onopen = () => setWsConnected(true);
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.type === 'aegis:threats') {
        setAlerts(prev => [data.threat, ...prev.slice(0, 50)]);
        setAttackerIps(prev => [...new Set([...prev, data.threat.src_ip])]);
      }
    };
    ws.onclose = () => setWsConnected(false);

    return () => ws.close();
  }, []);

  // Fetch stats
  useEffect(() => {
    const interval = setInterval(() => {
      fetch('http://localhost:8000/api/stats').then(r => r.json()).then(setStats);
      fetch('http://localhost:8000/api/pending-actions').then(r => r.json()).then(setPendingActions);
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  const approveAction = async (actionId, approved) => {
    await fetch('http://localhost:8000/api/approve-action', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({action_id: actionId, approved})
    });
    setPendingActions(prev => prev.filter(a => a.action_id !== actionId));
  };

  const generateReport = async () => {
    const report = await fetch('http://localhost:8000/api/generate-report').then(r => r.json());
    alert(JSON.stringify(report, null, 2));
  };

  const getSeverityColor = (severity) => severity > 0.7 ? '#ff4444' : severity > 0.4 ? '#ff8800' : '#44ff44';

  return (
    <div className="app">
      <header>
        <h1>⚔️ AEGIS SOC Dashboard</h1>
        <div className={`status ${wsConnected ? 'online' : 'offline'}`}>
          {wsConnected ? '🟢 LIVE' : '🔴 DISCONNECTED'}
        </div>
      </header>

      <div className="grid">
        {/* Threat Map */}
        <div className="panel threat-map">
          <h3>🌐 Threat Map</h3>
          <svg viewBox="0 0 400 300" className="map-svg">
            {/* Central AEGIS */}
            <circle cx="200" cy="150" r="30" fill="#00aa88" stroke="white" strokeWidth="2">
              <title>AEGIS Core</title>
            </circle>
            <text x="200" y="155" textAnchor="middle" fill="white" fontSize="12">AEGIS</text>
            
            {/* Attacker nodes */}
            {attackerIps.slice(0, 10).map((ip, i) => (
              <g key={ip}>
                <circle cx={200 + 80 * Math.cos((i / 10) * Math.PI * 2)} cy={150 + 60 * Math.sin((i / 10) * Math.PI * 2)} r="8" fill="#ff4444" stroke="orange" strokeWidth="1">
                  <title>{ip}</title>
                </circle>
                <line x1="200" y1="150" x2={200 + 80 * Math.cos((i / 10) * Math.PI * 2)} y2={150 + 60 * Math.sin((i / 10) * Math.PI * 2)} stroke="red" strokeWidth="1" opacity="0.6" />
              </g>
            ))}
          </svg>
          <div className="map-legend">
            {attackerIps.length} Active Attackers
          </div>
        </div>

        {/* Live Alerts */}
        <div className="panel live-alerts">
          <h3>🚨 Live Alerts ({alerts.length})</h3>
          <div ref={alertsRef} className="alerts-list">
            {alerts.map((alert, i) => (
              <div key={i} className="alert" style={{borderLeftColor: getSeverityColor(alert.severity)}}>
                <div className="alert-header">
                  <span className="type">{alert.threat_type}</span>
                  <span className="time">{new Date(alert.timestamp).toLocaleTimeString()}</span>
                </div>
                <div className="alert-body">
                  <strong>{alert.src_ip}</strong> → {alert.dst_ip} | {alert.severity*100 | 0}%
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Stats */}
        <div className="panel stats">
          <h3>📊 Statistics</h3>
          <div className="stat-grid">
            {Object.entries(stats.threat_counts || {}).map(([type, count]) => (
              <div key={type} className="stat-item">
                <div className="stat-label">{type}</div>
                <div className="stat-value">{count}</div>
              </div>
            ))}
          </div>
        </div>

        {/* Pending Actions */}
        <div className="panel pending-actions">
          <h3>✅ Pending Approvals ({pendingActions.length})</h3>
          {pendingActions.map((action) => (
            <div key={action.action_id} className="action-item">
              <div>{action.action || 'BLOCK_IP'} {action.threat?.src_ip}</div>
              <div className="action-buttons">
                <button onClick={() => approveAction(action.action_id, true)} className="btn approve">✅ Approve</button>
                <button onClick={() => approveAction(action.action_id, false)} className="btn deny">❌ Deny</button>
              </div>
            </div>
          ))}
          <button onClick={generateReport} className="btn full-width">📋 Generate SALUTE Report</button>
        </div>
      </div>

      <style jsx>{`
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Courier New', monospace; background: #0a0a0a; color: #00ff88; }
        .app { max-width: 1400px; margin: 0 auto; padding: 20px; }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        header h1 { color: #00ff88; }
        .status { padding: 8px 16px; border-radius: 20px; font-weight: bold; }
        .status.online { background: #004d00; }
        .status.offline { background: #4d0000; }
        .grid { display: grid; grid-template-columns: 1fr 2fr 1fr 1fr; gap: 20px; }
        .panel { background: #1a1a1a; border-radius: 10px; padding: 20px; border: 1px solid #333; }
        .panel h3 { margin-bottom: 15px; color: #00ff88; }
        .threat-map { grid-column: span 1; height: 300px; }
        .map-svg { width: 100%; height: 200px; }
        .live-alerts { grid-column: span 2; height: 400px; }
        .alerts-list { height: 320px; overflow-y: auto; }
        .alert { margin-bottom: 10px; padding: 10px; background: #2a2a2a; border-left: 4px solid; border-radius: 4px; }
        .alert-header { display: flex; justify-content: space-between; font-size: 12px; margin-bottom: 5px; }
        .stats, .pending-actions { height: 400px; }
        .stat-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
        .stat-item { text-align: center; padding: 10px; }
        .stat-label { font-size: 12px; opacity: 0.7; }
        .stat-value { font-size: 24px; font-weight: bold; color: #00ff88; }
        .action-item { margin-bottom: 15px; padding: 10px; background: #2a2a2a; border-radius: 4px; }
        .action-buttons { margin-top: 10px; }
        .btn { padding: 8px 16px; border: none; border-radius: 4px; cursor: pointer; margin-right: 5px; font-size: 12px; }
        .btn.approve { background: #004d00; color: white; }
        .btn.deny { background: #4d0000; color: white; }
        .btn.full-width { width: 100%; background: #0066cc; color: white; margin-top: 10px; }
      `}</style>
    </div>
  );
};

export default App;

