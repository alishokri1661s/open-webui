/** Shared aircraft colors so the table, legend and map always agree. */
export const FLIGHT_PALETTE = [
	'#38bdf8',
	'#fb923c',
	'#34d399',
	'#f472b6',
	'#a78bfa',
	'#facc15',
	'#22d3ee',
	'#f87171',
	'#4ade80',
	'#c084fc'
];

export const flightColor = (id: string): string => {
	let hash = 0;
	for (let index = 0; index < id.length; index += 1) {
		hash = (hash * 31 + id.charCodeAt(index)) % 9973;
	}
	return FLIGHT_PALETTE[hash % FLIGHT_PALETTE.length];
};
