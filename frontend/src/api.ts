const API_BASE = '/api';

export interface LogEntry {
  id: number;
  timestamp: string;
  type: 'meal' | 'flare' | 'medication' | 'note';
  raw_input?: string;
  parsed_ingredients?: string;
  parse_status?: string;
  severity?: number;
  medication_name?: string;
  medication_dose?: string;
  notes?: string;
  images?: string[];
}

export interface CreateLogEntry {
  timestamp: string;
  type: 'meal' | 'flare' | 'medication' | 'note';
  raw_input?: string;
  severity?: number;
  medication_name?: string;
  medication_dose?: string;
  notes?: string;
  barcode_ingredients?: string;
}

export interface AnalysisResult {
  stats: Array<{
    ingredient: string;
    lift: number;
    flare_freq: number;
    baseline_freq: number;
    flare_appearances: number;
    confounded: number;
  }>;
  summary: string;
  warning?: string;
}

export async function createLogEntry(entry: CreateLogEntry): Promise<{ id: number }> {
  const resp = await fetch(`${API_BASE}/log`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(entry),
  });
  if (!resp.ok) throw new Error(`Failed to create entry: ${resp.status}`);
  return resp.json();
}

export async function getLogEntries(params?: { type?: string; from?: string; to?: string }): Promise<LogEntry[]> {
  const query = new URLSearchParams();
  if (params?.type) query.set('type', params.type);
  if (params?.from) query.set('from', params.from);
  if (params?.to) query.set('to', params.to);
  const resp = await fetch(`${API_BASE}/logs?${query}`);
  if (!resp.ok) throw new Error(`Failed to fetch entries: ${resp.status}`);
  return resp.json();
}

export async function updateLogEntry(id: number, update: Partial<CreateLogEntry>): Promise<void> {
  const resp = await fetch(`${API_BASE}/log/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  if (!resp.ok) throw new Error(`Failed to update entry: ${resp.status}`);
}

export async function deleteLogEntry(id: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/log/${id}`, { method: 'DELETE' });
  if (!resp.ok) throw new Error(`Failed to delete entry: ${resp.status}`);
}

export async function startAnalysis(useLikely: boolean = false): Promise<{ job_id: string }> {
  const resp = await fetch(`${API_BASE}/analyse`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ use_likely: useLikely }),
  });
  if (!resp.ok) throw new Error(`Failed to start analysis: ${resp.status}`);
  return resp.json();
}

export async function getAnalysisResult(jobId: string): Promise<AnalysisResult & { status: string }> {
  const resp = await fetch(`${API_BASE}/analyse/${jobId}`);
  if (!resp.ok) throw new Error(`Failed to fetch analysis: ${resp.status}`);
  return resp.json();
}

export async function subscribePush(subscription: PushSubscription): Promise<void> {
  const json = subscription.toJSON();
  const resp = await fetch(`${API_BASE}/push/subscribe`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ endpoint: json.endpoint, keys: json.keys }),
  });
  if (!resp.ok) throw new Error(`Failed to subscribe: ${resp.status}`);
}

export async function uploadImage(entryId: number, file: File): Promise<{ id: number; path: string }> {
  const form = new FormData();
  form.append('file', file);
  const resp = await fetch(`${API_BASE}/log/${entryId}/image`, {
    method: 'POST',
    body: form,
  });
  if (!resp.ok) throw new Error(`Failed to upload image: ${resp.status}`);
  return resp.json();
}

export async function reparseEntry(id: number): Promise<void> {
  const resp = await fetch(`${API_BASE}/log/${id}/reparse`, { method: 'POST' });
  if (!resp.ok) throw new Error(`Failed to reparse: ${resp.status}`);
}

export async function reparseAllFailed(): Promise<{ entries: number }> {
  const resp = await fetch(`${API_BASE}/reparse-failed`, { method: 'POST' });
  if (!resp.ok) throw new Error(`Failed to reparse: ${resp.status}`);
  return resp.json();
}

export async function lookupBarcode(upc: string): Promise<{ ingredients: string; name: string }> {
  const resp = await fetch(`${API_BASE}/barcode/${upc}`, { method: 'POST' });
  if (!resp.ok) throw new Error(`Barcode lookup failed: ${resp.status}`);
  return resp.json();
}
