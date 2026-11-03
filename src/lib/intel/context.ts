import type {
	IntelFlightRow,
	IntelSearchHit,
	IntelTrajectory,
	IntelTrajectoryPoint
} from '$lib/apis/intel';

export type Citation = {
	label: string;
	detail?: string;
};

export type PreparedContext = {
	/** Text block appended to the user message. Empty when nothing was retrieved. */
	context: string;
	citations: Citation[];
};

const STOP_WORDS = new Set([
	'the',
	'and',
	'for',
	'with',
	'from',
	'that',
	'this',
	'what',
	'which',
	'when',
	'where',
	'how',
	'why',
	'are',
	'was',
	'were',
	'will',
	'would',
	'could',
	'should',
	'about',
	'into',
	'than',
	'then',
	'there',
	'their',
	'them',
	'they',
	'have',
	'has',
	'had',
	'you',
	'your',
	'our',
	'can',
	'does',
	'did',
	'not',
	'all',
	'any',
	'each',
	'more',
	'most',
	'some',
	'also',
	'been',
	'being',
	'between',
	'over',
	'under',
	'after',
	'before',
	'چیست',
	'چگونه',
	'چرا',
	'کدام',
	'کجا',
	'چه',
	'را',
	'از',
	'به',
	'با',
	'که',
	'این',
	'آن',
	'برای',
	'در',
	'و',
	'یا',
	'است',
	'هستند',
	'بود',
	'شده',
	'می'
]);

export const tokenize = (text: string): string[] =>
	(text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? []).filter(
		(token) => token.length > 1 && !STOP_WORDS.has(token)
	);

/** Split a document into overlapping chunks at paragraph boundaries. */
export const chunkText = (text: string, size = 1600, overlap = 220): string[] => {
	const normalized = text
		.replace(/\r\n/g, '\n')
		.replace(/[ \t]+/g, ' ')
		.trim();
	if (!normalized) return [];
	if (normalized.length <= size) return [normalized];

	const paragraphs = normalized.split(/\n{2,}/);
	const chunks: string[] = [];
	let current = '';

	for (const paragraph of paragraphs) {
		if (current.length + paragraph.length + 2 <= size) {
			current = current ? `${current}\n\n${paragraph}` : paragraph;
			continue;
		}
		if (current) {
			chunks.push(current);
			current = '';
		}
		if (paragraph.length <= size) {
			current = paragraph;
			continue;
		}
		// Very long paragraph: hard split with overlap so we never lose a sentence
		// completely at a boundary.
		let index = 0;
		while (index < paragraph.length) {
			const end = Math.min(paragraph.length, index + size);
			chunks.push(paragraph.slice(index, end));
			if (end === paragraph.length) break;
			index = Math.max(index + 1, end - overlap);
		}
	}

	if (current) {
		// Merge a tiny tail into the previous chunk when possible.
		const tail = current.trim();
		if (tail.length < 240 && chunks.length) {
			chunks[chunks.length - 1] = `${chunks[chunks.length - 1]}\n\n${tail}`;
		} else {
			chunks.push(tail);
		}
	}
	return chunks.filter((chunk) => chunk.trim().length > 0);
};

type ScoredChunk = {
	fileId: string;
	fileName: string;
	index: number;
	text: string;
	score: number;
};

/**
 * Lightweight BM25-ish ranking that runs in the browser: no embeddings, no
 * network, no extra services. Perfect for an offline deployment.
 */
export const rankChunks = (
	files: { id: string; name: string; text: string }[],
	question: string
): ScoredChunk[] => {
	const queryTokens = Array.from(new Set(tokenize(question)));
	const chunks: {
		fileId: string;
		fileName: string;
		index: number;
		text: string;
		tokens: string[];
	}[] = [];

	for (const file of files) {
		chunkText(file.text).forEach((text, index) => {
			chunks.push({ fileId: file.id, fileName: file.name, index, text, tokens: tokenize(text) });
		});
	}
	if (!chunks.length) return [];

	const documentFrequency = new Map<string, number>();
	for (const chunk of chunks) {
		for (const token of new Set(chunk.tokens)) {
			documentFrequency.set(token, (documentFrequency.get(token) ?? 0) + 1);
		}
	}

	const total = chunks.length;
	const averageLength = chunks.reduce((sum, chunk) => sum + chunk.tokens.length, 0) / total || 1;
	const k1 = 1.4;
	const b = 0.75;

	return chunks
		.map((chunk) => {
			const frequencies = new Map<string, number>();
			for (const token of chunk.tokens) frequencies.set(token, (frequencies.get(token) ?? 0) + 1);

			let score = 0;
			for (const token of queryTokens) {
				const frequency = frequencies.get(token) ?? 0;
				if (!frequency) continue;
				const df = documentFrequency.get(token) ?? 0;
				const idf = Math.log(1 + (total - df + 0.5) / (df + 0.5));
				score +=
					idf *
					((frequency * (k1 + 1)) /
						(frequency + k1 * (1 - b + (b * chunk.tokens.length) / averageLength)));
			}

			// Slight boost when the file name itself matches the query (handy for
			// questions like "what does the fuel report say?").
			const nameTokens = tokenize(chunk.fileName);
			if (queryTokens.some((token) => nameTokens.includes(token))) score *= 1.15;

			return { ...chunk, score };
		})
		.sort((a, b2) => b2.score - a.score);
};

export const buildFileContext = (
	files: { id: string; name: string; text: string }[],
	question: string,
	budget = 9000
): PreparedContext => {
	const ranked = rankChunks(files, question);
	if (!ranked.length) return { context: '', citations: [] };

	const picked: ScoredChunk[] = [];
	let used = 0;

	// Always give the model something even when no keyword matches (e.g. "summarise it").
	const pool = ranked.some((chunk) => chunk.score > 0)
		? ranked.filter((chunk) => chunk.score > 0)
		: ranked.slice(0, Math.max(2, Math.ceil(files.length * 2)));

	for (const chunk of pool) {
		if (used + chunk.text.length > budget) continue;
		picked.push(chunk);
		used += chunk.text.length;
		if (picked.length >= 10) break;
	}

	if (!picked.length && ranked[0]) {
		picked.push(ranked[0]);
	}

	const blocks = picked.map((chunk, index) => {
		return `[${index + 1}] file="${chunk.fileName}" chunk=${chunk.index + 1}\n${chunk.text}`;
	});

	const citations: Citation[] = picked.map((chunk) => ({
		label: chunk.fileName,
		detail: `#${chunk.index + 1}`
	}));

	return { context: blocks.join('\n\n---\n\n'), citations };
};

export const buildSearchContext = (hits: IntelSearchHit[], budget = 9000): PreparedContext => {
	if (!hits.length) return { context: '', citations: [] };

	const blocks: string[] = [];
	const citations: Citation[] = [];
	let used = 0;

	hits.forEach((hit, index) => {
		let body: string;
		try {
			body = JSON.stringify(hit.document, null, 1);
		} catch {
			body = String(hit.document);
		}
		const block = `[${index + 1}] document_id="${hit.id}"${hit.callsign ? ` callsign="${hit.callsign}"` : ''}${
			hit.time ? ` time="${hit.time}"` : ''
		}\n${hit.highlights.length ? `${hit.highlights.join('\n')}\n` : ''}${body}`;

		if (used + block.length > budget && blocks.length) return;
		blocks.push(block);
		used += block.length;
		citations.push({
			label: hit.callsign || hit.id,
			detail:
				hit.score !== null && hit.score !== undefined ? `score ${hit.score.toFixed(2)}` : undefined
		});
	});

	return { context: blocks.join('\n\n---\n\n'), citations };
};

export const haversineKm = (a: IntelTrajectoryPoint, b: IntelTrajectoryPoint): number => {
	const toRad = (value: number) => (value * Math.PI) / 180;
	const radius = 6371;
	const dLat = toRad(b.lat - a.lat);
	const dLon = toRad(b.lon - a.lon);
	const lat1 = toRad(a.lat);
	const lat2 = toRad(b.lat);
	const h =
		Math.sin(dLat / 2) * Math.sin(dLat / 2) +
		Math.cos(lat1) * Math.cos(lat2) * Math.sin(dLon / 2) * Math.sin(dLon / 2);
	return 2 * radius * Math.asin(Math.min(1, Math.sqrt(h)));
};

const describePoint = (point: IntelTrajectoryPoint): string => {
	const parts = [`${point.lat.toFixed(3)},${point.lon.toFixed(3)}`];
	if (point.alt !== undefined && point.alt !== null) parts.push(`FL${Math.round(point.alt / 100)}`);
	if (point.ts) parts.push(point.ts);
	return parts.join(' ');
};

export const describeFlight = (row: IntelFlightRow): string => {
	const route =
		row.origin || row.destination ? ` route ${row.origin ?? '?'} → ${row.destination ?? '?'}` : '';
	const details = [
		`id=${row.id}`,
		`callsign=${row.callsign}`,
		route.trim(),
		row.status ? `status=${row.status}` : '',
		row.registration ? `registration=${row.registration}` : '',
		row.aircraft_type ? `type=${row.aircraft_type}` : '',
		row.altitude !== null && row.altitude !== undefined
			? `altitude=${Math.round(row.altitude)}ft`
			: '',
		row.speed !== null && row.speed !== undefined ? `speed=${Math.round(row.speed)}kt` : '',
		row.heading !== null && row.heading !== undefined ? `heading=${Math.round(row.heading)}°` : '',
		row.lat !== null && row.lon !== null
			? `last_position=${row.lat?.toFixed(4)},${row.lon?.toFixed(4)}`
			: '',
		row.time ? `last_seen=${row.time}` : ''
	];
	return details.filter(Boolean).join(' ');
};

export const buildFlightsContext = (
	rows: IntelFlightRow[],
	trajectories: Map<string, IntelTrajectory>,
	selectedIds: string[],
	budget = 10000
): PreparedContext => {
	const selected = rows.filter((row) => selectedIds.includes(row.id));
	const focus = selected.length ? selected : rows.slice(0, 12);
	if (!focus.length) return { context: '', citations: [] };

	const blocks: string[] = [];
	const citations: Citation[] = [];
	let used = 0;

	// Dataset level statistics help the model answer aggregate questions even
	// when the user only selected a couple of aircraft.
	const statusCounts = new Map<string, number>();
	const routeCounts = new Map<string, number>();
	for (const row of rows) {
		const status = row.status || 'unknown';
		statusCounts.set(status, (statusCounts.get(status) ?? 0) + 1);
		const route = row.origin && row.destination ? `${row.origin}-${row.destination}` : '';
		if (route) routeCounts.set(route, (routeCounts.get(route) ?? 0) + 1);
	}
	const summary = [
		`Table window contains ${rows.length} aircraft (latest state per aircraft).`,
		statusCounts.size
			? `Status distribution: ${Array.from(statusCounts.entries())
					.sort((a, b) => b[1] - a[1])
					.map(([status, count]) => `${status}=${count}`)
					.join(', ')}.`
			: '',
		routeCounts.size
			? `Top routes: ${Array.from(routeCounts.entries())
					.sort((a, b) => b[1] - a[1])
					.slice(0, 8)
					.map(([route, count]) => `${route}(${count})`)
					.join(', ')}.`
			: ''
	]
		.filter(Boolean)
		.join(' ');

	blocks.push(`[dataset]\n${summary}`);
	used += summary.length;

	for (const [index, row] of focus.entries()) {
		const trajectory = trajectories.get(row.id);
		const lines: string[] = [`[aircraft ${index + 1}] ${describeFlight(row)}`];

		if (trajectory?.points?.length) {
			const points = trajectory.points;
			let distance = 0;
			for (let i = 1; i < points.length; i += 1) distance += haversineKm(points[i - 1], points[i]);
			lines.push(
				`trajectory: ${points.length} points from ${trajectory.start ?? '?'} to ${trajectory.end ?? '?'}, ~${distance.toFixed(0)} km flown.`
			);
			const step = Math.max(1, Math.floor(points.length / 12));
			const sampled = points.filter((_, pointIndex) => pointIndex % step === 0).slice(0, 14);
			lines.push(
				`trajectory samples (lat,lon FL timestamp): ${sampled.map(describePoint).join(' | ')}`
			);
		} else {
			lines.push('trajectory: not available for the current window.');
		}

		const block = lines.join('\n');
		if (used + block.length > budget && blocks.length > 1) continue;
		blocks.push(block);
		used += block.length;
		citations.push({
			label: row.callsign,
			detail: `${trajectory?.points?.length ?? 0} pts`
		});
	}

	return { context: blocks.join('\n\n'), citations };
};

export const composeUserMessage = (question: string, context: string): string => {
	if (!context.trim()) return question;
	return `${question}

---
Context (authoritative, retrieved from the user's local data; cite sources as [n] or by their label):
${context}`;
};
