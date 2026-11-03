import { WEBUI_API_BASE_URL } from '$lib/constants';

/**
 * Client for the offline "Intel" backend (`/api/v1/intel`).
 * The backend is intentionally thin: it exposes the Elasticsearch dataset and
 * the browser composes the prompts so chat reuse Open WebUI's normal model
 * pipeline (Ollama / OpenAI compatible, offline).
 */

export type IntelFlightRow = {
	id: string;
	doc_id?: string;
	callsign: string;
	time: string | null;
	lat: number | null;
	lon: number | null;
	altitude: number | null;
	speed: number | null;
	heading: number | null;
	status: string | null;
	points: number;
	source: 'elasticsearch' | 'demo' | string;
	origin?: string;
	destination?: string;
	registration?: string;
	aircraft_type?: string;
	[key: string]: unknown;
};

export type IntelFlightResponse = {
	items: IntelFlightRow[];
	total: number;
	aircraft: number;
	returned: number;
	source: string;
	range: { start: string; end: string };
	time_field: string | null;
	took_ms: number;
};

export type IntelTrajectoryPoint = {
	lat: number;
	lon: number;
	alt?: number;
	ts?: string;
};

export type IntelTrajectory = {
	id: string;
	points: IntelTrajectoryPoint[];
	count: number;
	source: string;
	start: string | null;
	end: string | null;
};

export type IntelSearchHit = {
	id: string;
	score: number | null;
	source: string;
	index?: string;
	document: Record<string, unknown>;
	snippet: string;
	highlights: string[];
	callsign?: string | null;
	time?: string | null;
};

export type IntelMeta = {
	enabled: boolean;
	demo: boolean;
	demo_mode?: string;
	ok?: boolean;
	elasticsearch: {
		configured: boolean;
		url: string;
		index: string;
		verify_certs?: boolean;
		connected?: boolean;
		cluster?: string;
		version?: string;
		doc_count?: number | null;
		schema_detected?: boolean;
		error?: string | null;
	};
	fields: Record<string, string | null>;
	query_fields?: string[];
	default_lookback_hours: number;
	max_rows: number;
	rag_top_k: number;
	map_tile_url?: string;
	warnings?: string[];
	topic?: { name?: string; prompt?: string; suggestions?: string[] };
	demo_aircraft?: number;
};

const request = async (path: string, token: string, options: RequestInit = {}) => {
	const res = await fetch(`${WEBUI_API_BASE_URL}/intel${path}`, {
		...options,
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			...(token ? { authorization: `Bearer ${token}` } : {}),
			...(options.headers ?? {})
		}
	});

	if (!res.ok) {
		let detail = `Request failed with status ${res.status}`;
		try {
			const payload = await res.json();
			detail = payload?.detail || detail;
		} catch {
			// ignore non JSON errors
		}
		throw new Error(detail);
	}

	return res.json();
};

export const getIntelMeta = async (token: string, force = false): Promise<IntelMeta> => {
	return request(`/meta${force ? '?force=true' : ''}`, token);
};

export const getIntelFlights = async (
	token: string,
	params: {
		start?: string | null;
		end?: string | null;
		hours?: number | null;
		q?: string;
		size?: number;
	} = {}
): Promise<IntelFlightResponse> => {
	const search = new URLSearchParams();
	if (params.start) search.set('start', params.start);
	if (params.end) search.set('end', params.end);
	if (params.hours) search.set('hours', String(params.hours));
	if (params.q) search.set('q', params.q);
	if (params.size) search.set('size', String(params.size));

	return request(`/flights?${search.toString()}`, token);
};

export const getIntelTrajectory = async (
	token: string,
	identifier: string,
	params: { start?: string | null; end?: string | null; hours?: number | null } = {}
): Promise<IntelTrajectory> => {
	const search = new URLSearchParams();
	if (params.start) search.set('start', params.start);
	if (params.end) search.set('end', params.end);
	if (params.hours) search.set('hours', String(params.hours));

	return request(
		`/flights/${encodeURIComponent(identifier)}/trajectory?${search.toString()}`,
		token
	);
};

/** Raw Elasticsearch search over the configured index. Not wired into the default
 *  UI (the flight tab builds its context from the table), but handy for custom
 *  topic grounding or for extending the workspace. */
export const searchIntelDocuments = async (
	token: string,
	body: {
		query: string;
		top_k?: number;
		start?: string | null;
		end?: string | null;
		hours?: number | null;
		filters?: Record<string, unknown>;
	}
): Promise<{ hits: IntelSearchHit[]; total: number; source: string; took_ms: number }> => {
	return request(`/search`, token, { method: 'POST', body: JSON.stringify(body) });
};
