<script lang="ts">
	import { onDestroy, onMount } from 'svelte';
	import type { Readable } from 'svelte/store';
	import type { IntelFlightRow, IntelTrajectory } from '$lib/apis/intel';
	import { createIntelTranslator } from '$lib/intel/i18n';
	import { flightColor } from '$lib/intel/colors';
	import { getContext } from 'svelte';

	export let rows: IntelFlightRow[] = [];
	export let trajectories: Record<string, IntelTrajectory> = {};
	export let selectedIds: string[] = [];
	export let focusId: string | null = null;
	export let tileUrl = '';
	export let onToggle: ((id: string) => void) | null = null;

	const i18n = getContext<Readable<any>>('i18n');
	$: t = createIntelTranslator($i18n?.locale);

	let container: HTMLDivElement;
	let map: any = null;
	let L: any = null;
	let routesLayer: any = null;
	let markersLayer: any = null;
	let baseLayer: any = null;
	let resizeObserver: ResizeObserver | null = null;
	let themeObserver: MutationObserver | null = null;
	let dark = false;
	let ready = false;
	let fittedKey = '';
	let lastFocus: string | null = null;
	let hadSize = false;

	const colorFor = flightColor;

	/** Leaflet divIcons/popups take raw HTML — never interpolate data unescaped. */
	const esc = (value: unknown): string =>
		String(value ?? '')
			.replaceAll('&', '&amp;')
			.replaceAll('<', '&lt;')
			.replaceAll('>', '&gt;')
			.replaceAll('"', '&quot;')
			.replaceAll("'", '&#39;');

	const isDark = () =>
		typeof document !== 'undefined' && document.documentElement.classList.contains('dark');

	const planeIcon = (color: string, heading: number | null) => {
		const rotation = Number.isFinite(heading as number) ? heading : 0;
		const html = `
			<div class="intel-plane" style="--plane-color:${color}">
				<svg viewBox="0 0 24 24" width="26" height="26" style="transform: rotate(${rotation}deg)">
					<path d="M12 2c.9 0 1.6 1.1 1.6 2.5v4.2l7 4.1v2.1l-7-2.1v4.4l2.4 1.8v1.6L12 19.7l-4 0.9v-1.6l2.4-1.8v-4.4l-7 2.1v-2.1l7-4.1V4.5C10.4 3.1 11.1 2 12 2z"
						fill="${color}" stroke="rgba(0,0,0,.35)" stroke-width="0.6"/>
				</svg>
			</div>`;
		return L.divIcon({
			className: 'intel-plane-icon',
			html,
			iconSize: [26, 26],
			iconAnchor: [13, 13]
		});
	};

	const drawBase = () => {
		if (!map || !L) return;
		dark = isDark();
		map.getContainer().style.background = dark ? '#060b18' : '#dbeafe';

		if (baseLayer) map.removeLayer(baseLayer);

		if (tileUrl) {
			baseLayer = L.tileLayer(tileUrl, {
				maxZoom: 12,
				attribution: '&copy; map tiles'
			}).addTo(map);
			return;
		}

		// Fully offline vector basemap (Natural Earth 110m, bundled with the app).
		const land = L.geoJSON(undefined, {
			style: {
				color: dark ? '#1e293b' : '#94a3b8',
				weight: 0.7,
				fillColor: dark ? '#0f172a' : '#f8fafc',
				fillOpacity: 1
			},
			interactive: false
		});
		baseLayer = land.addTo(map);
		if ((window as any).__intelCountries) {
			land.addData((window as any).__intelCountries);
		}

		// Subtle graticule so the empty ocean still reads as a map.
		const gridStyle = {
			color: dark ? '#1e293b' : '#bfdbfe',
			weight: 0.5,
			opacity: 0.7,
			interactive: false
		};
		for (let lat = -60; lat <= 60; lat += 30) {
			L.polyline(
				[
					[lat, -180],
					[lat, 180]
				],
				gridStyle
			).addTo(baseLayer);
		}
		for (let lon = -180; lon < 180; lon += 30) {
			L.polyline(
				[
					[-85, lon],
					[85, lon]
				],
				gridStyle
			).addTo(baseLayer);
		}
	};

	const drawFlights = () => {
		if (!map || !L || !routesLayer || !markersLayer) return;
		routesLayer.clearLayers();
		markersLayer.clearLayers();

		const selected = new Set(selectedIds);
		const bounds: any[] = [];

		// Every aircraft in the table gets a muted dot for spatial context.
		for (const row of rows) {
			if (selected.has(row.id)) continue;
			if (row.lat === null || row.lon === null) continue;
			const dot = L.circleMarker([row.lat as number, row.lon as number], {
				radius: 3,
				color: dark ? '#475569' : '#94a3b8',
				fillColor: dark ? '#334155' : '#cbd5e1',
				fillOpacity: 0.9,
				weight: 1
			}).addTo(markersLayer);
			dot.bindTooltip(esc(row.callsign ?? row.id), {
				direction: 'top',
				className: 'intel-tooltip'
			});
			dot.on('click', () => onToggle?.(row.id));
		}

		for (const id of selectedIds) {
			const row = rows.find((item) => item.id === id);
			const trajectory = trajectories[id];
			const color = colorFor(id);
			const points = (trajectory?.points ?? [])
				.filter((point) => Number.isFinite(point.lat) && Number.isFinite(point.lon))
				.map((point) => [point.lat, point.lon]);

			let last = points[points.length - 1];
			if (!last && row && row.lat !== null && row.lon !== null) {
				last = [row.lat as number, row.lon as number];
			}

			if (points.length > 1) {
				L.polyline(points, {
					color,
					weight: 2.2,
					opacity: 0.85,
					interactive: false
				}).addTo(routesLayer);

				L.circleMarker(points[0], {
					radius: 3,
					color,
					fillColor: color,
					fillOpacity: 1,
					weight: 1,
					opacity: 0.8
				}).addTo(routesLayer);
			}

			if (last) {
				bounds.push(last);
				const callsignLabel = row?.callsign ?? id;
				const marker = L.marker(last, {
					icon: planeIcon(color, row?.heading ?? null),
					riseOnHover: true,
					zIndexOffset: 500
				}).addTo(markersLayer);

				const title = row
					? `<div class="intel-popup">
							<div class="intel-popup-title" style="color:${color}">${esc(row.callsign)}</div>
							<div class="intel-popup-row">${esc(row.origin ?? '?')} → ${esc(row.destination ?? '?')}</div>
							<div class="intel-popup-row">${esc(row.status ?? '')}</div>
							<div class="intel-popup-row">${
								row.altitude !== null && row.altitude !== undefined
									? `${Math.round(row.altitude)} ft`
									: '—'
							} · ${row.speed !== null && row.speed !== undefined ? `${Math.round(row.speed)} kt` : '—'}</div>
							<div class="intel-popup-row intel-popup-mono">${(last[0] as number).toFixed(3)}, ${(last[1] as number).toFixed(3)}</div>
						</div>`
					: callsignLabel;

				marker.bindPopup(title, { closeButton: false, className: 'intel-popup-wrapper' });
				marker.bindTooltip(esc(callsignLabel), {
					direction: 'top',
					className: 'intel-tooltip',
					offset: [0, -10],
					permanent: selectedIds.length <= 6
				});
			}
		}

		const key = [...selectedIds].sort().join('|');
		if (key && key !== fittedKey) {
			fittedKey = key;
			if (bounds.length === 1) {
				map.flyTo(bounds[0], Math.max(map.getZoom(), 5), { duration: 0.6 });
			} else if (bounds.length > 1) {
				map.flyToBounds(L.latLngBounds(bounds).pad(0.25), { duration: 0.7, maxZoom: 7 });
			}
		}
		if (!key) fittedKey = '';
	};

	onMount(async () => {
		const [{ default: leaflet }] = await Promise.all([
			import('leaflet'),
			import('leaflet/dist/leaflet.css')
		]);
		L = leaflet;

		dark = isDark();
		map = L.map(container, {
			zoomControl: true,
			worldCopyJump: true,
			minZoom: 2,
			attributionControl: true,
			preferCanvas: true
		}).setView([30, 25], 3);
		map.attributionControl.setPrefix(false);

		if (!tileUrl) {
			try {
				const [world, topojson] = await Promise.all([
					import('world-atlas/countries-110m.json'),
					import('topojson-client')
				]);
				(window as any).__intelCountries = topojson.feature(
					world.default,
					(world.default as any).objects.countries
				);
				map.attributionControl.addAttribution('Offline basemap · Natural Earth');
			} catch (error) {
				console.warn('Intel map: could not load the offline basemap', error);
			}
		}

		routesLayer = L.layerGroup().addTo(map);
		markersLayer = L.layerGroup().addTo(map);
		ready = true;

		drawBase();
		drawFlights();
		requestAnimationFrame(() => map?.invalidateSize());

		if (typeof ResizeObserver !== 'undefined') {
			resizeObserver = new ResizeObserver(() => {
				map?.invalidateSize();
				// The workspace may be mounted while hidden (another tab is open); when it
				// becomes visible for the first time the map needs a real size and a refit.
				if (!hadSize) {
					const { width, height } = container.getBoundingClientRect();
					if (width > 0 && height > 0) {
						hadSize = true;
						fittedKey = '';
						drawFlights();
					}
				}
			});
			resizeObserver.observe(container);
		}

		if (typeof MutationObserver !== 'undefined') {
			themeObserver = new MutationObserver(() => {
				const nextDark = isDark();
				if (nextDark === dark) return;
				dark = nextDark;
				drawBase();
				drawFlights();
			});
			themeObserver.observe(document.documentElement, {
				attributes: true,
				attributeFilter: ['class']
			});
		}
	});

	// Redraw whenever the selection, data or theme changes.
	$: if (ready && map) {
		rows;
		selectedIds;
		trajectories;
		tileUrl;
		drawFlights();
	}

	let lastTileUrl = tileUrl;
	$: if (ready && map && tileUrl !== lastTileUrl) {
		lastTileUrl = tileUrl;
		drawBase();
		drawFlights();
	}

	$: if (ready && focusId && focusId !== lastFocus) {
		lastFocus = focusId;
		const row = rows.find((item) => item.id === focusId);
		const point = row && row.lat !== null && row.lon !== null ? [row.lat, row.lon] : null;
		if (point) map?.flyTo(point, Math.max(map.getZoom(), 6), { duration: 0.6 });
	}

	onDestroy(() => {
		resizeObserver?.disconnect();
		themeObserver?.disconnect();
		map?.remove();
		map = null;
	});
</script>

<div
	class="relative h-full w-full overflow-hidden rounded-xl border border-gray-100 dark:border-gray-850"
>
	<div bind:this={container} class="intel-map absolute inset-0 z-0"></div>

	<div
		class="pointer-events-none absolute bottom-2 start-2 z-[500] flex flex-col gap-1 rounded-lg bg-white/85 px-2 py-1.5 text-[10px] leading-4 text-gray-600 shadow-sm backdrop-blur dark:bg-gray-900/85 dark:text-gray-300"
	>
		<span class="font-medium">{t('Live map')}</span>
		<span>{tileUrl ? t('Online map tiles') : t('Offline vector basemap')}</span>
		{#if selectedIds.length}
			<span class="font-medium text-gray-500 dark:text-gray-400"
				>{selectedIds.length} / {rows.length}</span
			>
		{/if}
	</div>
</div>

<style>
	.intel-map {
		background: #dbeafe;
	}

	.intel-map :global(.leaflet-container) {
		background: transparent;
		font-family: inherit;
	}

	.intel-map :global(.leaflet-control-attribution) {
		background: rgba(255, 255, 255, 0.7);
		font-size: 9px;
		color: #64748b;
	}

	.intel-map :global(.leaflet-control-zoom a) {
		background: rgba(255, 255, 255, 0.85);
		color: #0f172a;
		border-color: rgba(148, 163, 184, 0.3);
	}

	.intel-map :global(.intel-plane-icon) {
		background: transparent;
		border: none;
	}

	.intel-map :global(.intel-plane) {
		position: relative;
		width: 26px;
		height: 26px;
		filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.4));
	}

	.intel-map :global(.intel-tooltip) {
		font-size: 10px;
		padding: 1px 5px;
		border: none;
		border-radius: 4px;
		box-shadow: 0 1px 4px rgba(0, 0, 0, 0.2);
	}

	.intel-map :global(.intel-popup-wrapper .leaflet-popup-content) {
		margin: 8px 10px;
	}

	.intel-map :global(.intel-popup) {
		font-size: 11px;
		line-height: 1.5;
		min-width: 120px;
	}

	.intel-map :global(.intel-popup-title) {
		font-weight: 700;
		font-size: 12px;
		margin-bottom: 2px;
	}

	.intel-map :global(.intel-popup-mono) {
		font-family: ui-monospace, SFMono-Regular, monospace;
		color: #64748b;
	}
</style>
