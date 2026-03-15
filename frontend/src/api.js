const API_BASE = '/api';

export async function fetchCampaigns() {
  const res = await fetch(`${API_BASE}/campaigns`);
  if (!res.ok) throw new Error('Failed to fetch campaigns');
  return res.json();
}

export async function fetchCampaignStatus(campaignId) {
  const res = await fetch(`${API_BASE}/campaign/${campaignId}/status`);
  if (!res.ok) throw new Error('Failed to fetch campaign status');
  return res.json();
}

export async function fetchCampaignLogs(campaignId) {
  const res = await fetch(`${API_BASE}/campaign/${campaignId}/logs`);
  if (!res.ok) throw new Error('Failed to fetch campaign logs');
  return res.json();
}

export async function submitCampaign({ brief, target_segment, product_name }) {
  const res = await fetch(`${API_BASE}/campaign/submit`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ brief, target_segment, product_name }),
  });
  if (!res.ok) throw new Error('Failed to submit campaign');
  return res.json();
}

export async function runSimulation(campaignId, recipientCount = 200, seed = null) {
  const res = await fetch(`${API_BASE}/simulator/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ campaign_id: campaignId, recipient_count: recipientCount, seed }),
  });
  if (!res.ok) throw new Error('Failed to run simulation');
  return res.json();
}

export async function fetchSimulationReport(campaignId) {
  const res = await fetch(`${API_BASE}/simulator/report/${campaignId}`);
  if (!res.ok && res.status !== 404) throw new Error('Failed to fetch report');
  if (res.status === 404) return null;
  return res.json();
}

// Pipeline control
export async function runPipeline(campaignId) {
  const res = await fetch(`${API_BASE}/pipeline/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ campaign_id: campaignId }),
  });
  if (!res.ok) throw new Error('Failed to start pipeline');
  return res.json();
}

export async function fetchPipelineState(campaignId) {
  const res = await fetch(`${API_BASE}/pipeline/state/${campaignId}`);
  if (!res.ok && res.status !== 404) throw new Error('Failed to fetch pipeline state');
  if (res.status === 404) return null;
  return res.json();
}

export async function approvePipeline(campaignId, scheduledSendTime = null) {
  const res = await fetch(`${API_BASE}/pipeline/approve/${campaignId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scheduled_send_time: scheduledSendTime }),
  });
  if (!res.ok) throw new Error('Failed to approve pipeline');
  return res.json();
}

export async function rejectPipeline(campaignId) {
  const res = await fetch(`${API_BASE}/pipeline/reject/${campaignId}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to reject pipeline');
  return res.json();
}

export async function fetchPipelineNodes() {
  const res = await fetch(`${API_BASE}/pipeline/nodes`);
  if (!res.ok) throw new Error('Failed to fetch pipeline nodes');
  return res.json();
}

// Optimizer control
export async function startOptimization(campaignId) {
  const res = await fetch(`${API_BASE}/optimizer/start/${campaignId}`, {
    method: 'POST',
  });
  if (!res.ok) throw new Error('Failed to start optimization');
  return res.json();
}

export async function fetchOptimizationStatus(campaignId) {
  const res = await fetch(`${API_BASE}/optimizer/status/${campaignId}`);
  if (!res.ok && res.status !== 404) throw new Error('Failed to fetch optimization status');
  if (res.status === 404) return null;
  return res.json();
}
