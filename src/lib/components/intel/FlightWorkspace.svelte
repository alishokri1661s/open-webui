<script lang="ts">
	import { getContext, onMount, onDestroy } from 'svelte';
	import type { Readable } from 'svelte/store';

	import {
		getIntelFlights,
		getIntelTrajectory,
		type IntelFlightRow,
		type IntelMeta,
		type IntelTrajectory
	} from '$lib/apis/intel';
	import { buildFlightsContext } from '$lib/intel/context';
	import { createIntelTranslator, formatDateTime, formatNumber } from '$lib/intel/i18n';
	import { flightColor } from '$lib/intel/colors';

	import ChatSurface from '$lib/components/intel/ChatSurface.svelte';
	import FlightMap from '$lib/components/intel/FlightMap.svelte';
	import FlightTable from '$lib/components/intel/FlightTable.svelte';

	import ArrowPathIcon from '$lib/components/icons/ArrowPath.svelte';
	import SearchIcon from '$lib/components/icons/Search.svelte';
	import XMarkIcon from '$lib/components/icons/XMark.svelte';
	import MapIcon from '$lib/components/icons/Map.svelte';
	import SparklesIcon from '$lib/components/icons/Sparkles.svelte';
	import InfoIcon from '$lib/components/icons/Info.svelte';

	export let meta: IntelMeta | null = null;
	export let modelId = '';

	const i18n = getContext<Readable<any>>('i18n');
	$: t = createIntelTranslator($i18n?.locale);
	$: locale = $i18n?.locale;
	$: isPersian = (locale ?? '').toLowerCase().startsWith('fa');

	const MAX_SELECTION = 20;
	const PRESETS = [
		{ hours: 1, label: 'Last hour' },
		{ hours: 6, label: 'Last 6 hours' },
		{ hours: 24, label: 'Last 24 hours' },
		{ hours: 168, label: 'Last 7 days' }
	];

	let presetHours: number | null = 24;
	let useCustom = false;
	let customStart = '';
	let customEnd = '';

	let query = '';
	let rows: IntelFlightRow[] = [];
	let loading = false;
	let error = '';
	let lastLoaded: string | null = null;
	let summary = { total: 0, aircraft: 0, returned: 0, source: '' };

	let selectedIds: string[] = [];
	let trajectories: Record<string, IntelTrajectory> = {};
	let loadingTrajectories: string[] = [];
	let focusId: string | null = null;
	let selectionNote = '';

	let chat: ChatSurface;
	let debounceTimer: ReturnType<typeof setTimeout> | null = null;
	let rowLimit = 300;
	let loadSequence = 0;
	let trajectoryTokens: Record<string, number> = {};

	$: tileUrl = meta?.map_tile_url ?? '';

	const inputClass =
		'rounded-lg border border-gray-200/80 bg-transparent px-2 py-1 text-xs text-gray-700 outline-none transition focus:border-gray-300 dark:border-gray-800 dark:text-gray-200';

	const toLocalInput = (date: Date) => {
		const offset = date.getTimezoneOffset();
		return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
	};

	const initialiseCustomRange = () => {
		if (customStart && customEnd) return;
		const end = new Date();
		const start = new Date(end.getTime() - 24 * 3600 * 1000);
		customStart = toLocalInput(start);
		customEnd = toLocalInput(end);
	};

	const rangeParams = () => {
		if (useCustom && customStart && customEnd) {
			const start = new Date(customStart);
			const end = new Date(customEnd);
			if (!Number.isNaN(start.getTime()) && !Number.isNaN(end.getTime())) {
				return { start: start.toISOString(), end: end.toISOString() };
			}
		}
		return { hours: presetHours ?? 24 };
	};

	const load = async () => {
		const sequence = ++loadSequence;
		loading = true;
		error = '';
		try {
			const response = await getIntelFlights(localStorage.token ?? '', {
				...rangeParams(),
				q: query.trim(),
				size: rowLimit
			});
			if (sequence !== loadSequence) return;
			rows = response.items ?? [];
			summary = {
				total: response.total ?? 0,
				aircraft: response.aircraft ?? rows.length,
				returned: response.returned ?? rows.length,
				source: response.source
			};
			lastLoaded = new Date().toISOString();

			// Drop selections that are no longer part of the result set.
			selectedIds = selectedIds.filter((id) => rows.some((row) => row.id === id));
			// Refresh trajectories for the remaining selection against the new window.
			for (const id of selectedIds) {
				delete trajectories[id];
			}
			trajectories = { ...trajectories };
			for (const id of selectedIds.slice(0, MAX_SELECTION)) {
				void fetchTrajectory(id, true);
			}
		} catch (err) {
			if (sequence !== loadSequence) return;
			error = err instanceof Error ? err.message : String(err);
			rows = [];
		} finally {
			if (sequence === loadSequence) loading = false;
		}
	};

	const fetchTrajectory = async (id: string, force = false) => {
		if (!force && (trajectories[id] || loadingTrajectories.includes(id))) return;
		// Only the newest request for an aircraft may write its trajectory, so a slow
		// response from an older time window can never overwrite a fresh one.
		const token = (trajectoryTokens[id] = (trajectoryTokens[id] ?? 0) + 1);
		if (!loadingTrajectories.includes(id)) {
			loadingTrajectories = [...loadingTrajectories, id];
		}
		try {
			const trajectory = await getIntelTrajectory(localStorage.token ?? '', id, rangeParams());
			if (trajectoryTokens[id] !== token) return;
			trajectories = { ...trajectories, [id]: trajectory };
		} catch (err) {
			console.warn('Intel: could not load trajectory', id, err);
		} finally {
			if (trajectoryTokens[id] === token) {
				loadingTrajectories = loadingTrajectories.filter((item) => item !== id);
			}
		}
	};

	const toggle = (id: string) => {
		if (selectedIds.includes(id)) {
			selectedIds = selectedIds.filter((item) => item !== id);
			selectionNote = '';
			return;
		}
		if (selectedIds.length >= MAX_SELECTION) {
			selectionNote = isPersian
				? `حداکثر ${MAX_SELECTION} هواپیما را می‌توان هم‌زمان روی نقشه دید.`
				: `Up to ${MAX_SELECTION} aircraft can be drawn at once.`;
			return;
		}
		selectionNote = '';
		selectedIds = [...selectedIds, id];
		void fetchTrajectory(id);
	};

	const toggleAll = (select: boolean) => {
		if (!select) {
			selectedIds = [];
			selectionNote = '';
			return;
		}
		const ids = rows
			.filter((row) => row.lat !== null && row.lon !== null)
			.slice(0, MAX_SELECTION)
			.map((row) => row.id);
		selectedIds = ids;
		if (rows.length > MAX_SELECTION) {
			selectionNote = isPersian
				? `فقط ${MAX_SELECTION} هواپیمای اول انتخاب شد.`
				: `Only the first ${MAX_SELECTION} aircraft were selected.`;
		}
		for (const id of ids) void fetchTrajectory(id);
	};

	const removeSelected = (id: string) => {
		selectedIds = selectedIds.filter((item) => item !== id);
	};

	const onPreset = (hours: number) => {
		useCustom = false;
		presetHours = hours;
		void load();
	};

	const applyCustom = () => {
		useCustom = true;
		void load();
	};

	const onQueryInput = () => {
		if (debounceTimer) clearTimeout(debounceTimer);
		debounceTimer = setTimeout(() => {
			void load();
		}, 450);
	};

	const systemPrompt = () => {
		const demoNote = meta?.demo
			? 'The dataset currently shown is a SYNTHETIC DEMO dataset. Say so if the user treats it as real operational data.'
			: '';
		return `You are the flight-intelligence analyst of a local, offline operations room. You answer questions about the aircraft in the user's Elasticsearch index using the context that is attached to each question (latest state per aircraft, dataset statistics and sampled trajectory points).

How to answer:
- Ground every factual claim in the attached context. If an aircraft or field is not present, say so plainly instead of guessing.
- Refer to aircraft by their callsign (and mention the id when useful).
- For questions about routes, use the trajectory samples: describe the direction of travel, the area covered, and the approximate distance flown.
- For comparisons, use compact tables or short bullet lists.
- Distinguish observations (what the data shows) from assessments (what it might mean).
- When the user asks about something outside the dataset, answer from general knowledge but label it clearly as general knowledge.
- Always answer in the language of the user's question.
${demoNote}`;
	};

	const prepareContext = async (question: string) => {
		return buildFlightsContext(rows, new Map(Object.entries(trajectories)), selectedIds);
	};

	const askAboutSelection = () => {
		if (!selectedIds.length) return;
		chat?.ask(
			isPersian
				? 'هواپیماهای انتخاب‌شده را تحلیل کن: مسیر، ارتفاع، وضعیت و هر نکته غیرعادی را مقایسه کن.'
				: 'Analyse the selected aircraft: compare their routes, altitudes and status, and flag anything unusual.'
		);
	};

	onMount(() => {
		initialiseCustomRange();
		void load();
	});

	onDestroy(() => {
		if (debounceTimer) clearTimeout(debounceTimer);
	});
</script>

<div class="flex h-full min-h-0 flex-col gap-3">
	<!-- Filters -->
	<div
		class="rounded-2xl border border-gray-100 bg-white p-2.5 dark:border-gray-850 dark:bg-gray-900"
	>
		<div class="flex flex-wrap items-center gap-2">
			<div
				class="flex items-center gap-0.5 rounded-lg bg-gray-100/70 p-0.5 dark:bg-gray-850"
				role="group"
				aria-label={t('Time window')}
			>
				{#each PRESETS as option (option.hours)}
					<button
						class="rounded-md px-2 py-1 text-[11px] font-medium transition {!useCustom &&
						presetHours === option.hours
							? 'bg-white text-gray-900 shadow-sm dark:bg-gray-800 dark:text-white'
							: 'text-gray-500 hover:text-gray-800 dark:text-gray-400 dark:hover:text-gray-200'}"
						on:click={() => onPreset(option.hours)}
					>
						{t(option.label)}
					</button>
				{/each}
			</div>

			<div class="flex items-center gap-1">
				<input
					type="datetime-local"
					bind:value={customStart}
					on:focus={initialiseCustomRange}
					class="{inputClass} {useCustom ? 'border-sky-400/60' : ''}"
					aria-label={t('From')}
					title={t('From')}
				/>
				<span class="text-[10px] text-gray-400">→</span>
				<input
					type="datetime-local"
					bind:value={customEnd}
					on:focus={initialiseCustomRange}
					class="{inputClass} {useCustom ? 'border-sky-400/60' : ''}"
					aria-label={t('To')}
					title={t('To')}
				/>
				<button
					class="rounded-lg border border-gray-200/80 px-2 py-1 text-[11px] font-medium text-gray-600 transition hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850"
					on:click={applyCustom}
				>
					{t('Apply')}
				</button>
			</div>

			<div class="relative min-w-40 flex-1">
				<SearchIcon
					className="pointer-events-none absolute start-2 top-1/2 size-3.5 -translate-y-1/2 text-gray-400"
					strokeWidth="1.8"
				/>
				<input
					type="text"
					bind:value={query}
					on:input={onQueryInput}
					placeholder={t('Callsign, route, status…')}
					class="{inputClass} w-full ps-7"
				/>
			</div>

			<button
				class="flex items-center gap-1.5 rounded-lg border border-gray-200/80 px-2 py-1 text-[11px] font-medium text-gray-600 transition hover:bg-gray-50 disabled:opacity-40 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850"
				on:click={() => load()}
				disabled={loading}
			>
				<ArrowPathIcon className="size-3.5 {loading ? 'animate-spin' : ''}" strokeWidth="1.8" />
				{t('Refresh')}
			</button>

			<div class="ms-auto flex items-center gap-2 text-[11px] text-gray-400">
				<span class="font-medium text-gray-600 dark:text-gray-300">
					{t('{n} aircraft', { n: formatNumber(summary.returned, locale) })}
				</span>
				<span>·</span>
				<span>{t('{n} documents', { n: formatNumber(summary.total, locale) })}</span>
				{#if summary.source === 'demo'}
					<span
						class="rounded-md bg-amber-100 px-1.5 py-0.5 text-[10px] font-semibold text-amber-700 dark:bg-amber-500/15 dark:text-amber-300"
					>
						{t('Demo data')}
					</span>
				{:else if lastLoaded}
					<span class="hidden items-center gap-1 sm:flex">
						<span class="size-1.5 rounded-full bg-emerald-500"></span>
						{formatDateTime(lastLoaded, locale)}
					</span>
				{/if}
			</div>
		</div>

		{#if error}
			<div
				class="mt-2 flex items-start gap-2 rounded-lg bg-red-50 px-2 py-1.5 text-[11px] text-red-600 dark:bg-red-500/10 dark:text-red-300"
			>
				<InfoIcon className="mt-0.5 size-3.5 shrink-0" strokeWidth="1.8" />
				<div class="min-w-0 flex-1">
					<span class="font-semibold">{t('Could not load flights')}: </span>{error}
				</div>
				<button class="font-semibold underline" on:click={() => load()}>{t('Retry')}</button>
			</div>
		{/if}

		{#if meta?.warnings?.length}
			<div
				class="mt-2 rounded-lg bg-amber-50 px-2 py-1.5 text-[11px] text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
			>
				{#each meta.warnings as warning, index (index)}
					<div>{warning}</div>
				{/each}
			</div>
		{/if}
	</div>

	<!-- Table · Map · Chat -->
	<div class="grid min-h-0 flex-1 grid-cols-1 gap-3 xl:grid-cols-12">
		<!-- Table -->
		<section
			class="flex min-h-0 flex-col rounded-2xl border border-gray-100 bg-white xl:col-span-4 dark:border-gray-850 dark:bg-gray-900"
		>
			<header
				class="flex items-center justify-between gap-2 border-b border-gray-100 px-2.5 py-1.5 dark:border-gray-850"
			>
				<div
					class="flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-200"
				>
					<MapIcon className="size-3.5 text-gray-400" strokeWidth="1.8" />
					{t('Aircraft')}
				</div>
				<div class="flex items-center gap-1">
					<button
						class="rounded-md px-1.5 py-0.5 text-[10px] font-medium text-gray-500 transition hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-850"
						on:click={() => toggleAll(true)}
					>
						{t('Select all')}
					</button>
					<button
						class="rounded-md px-1.5 py-0.5 text-[10px] font-medium text-gray-500 transition hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-850"
						on:click={() => toggleAll(false)}
					>
						{t('Clear')}
					</button>
				</div>
			</header>

			<div class="min-h-0 flex-1 overflow-hidden">
				<FlightTable
					{rows}
					{selectedIds}
					{loading}
					onToggle={toggle}
					onToggleAll={toggleAll}
					onFocus={(id) => (focusId = id)}
				/>
			</div>

			<div
				class="border-t border-gray-100 px-2.5 py-1 text-[10px] text-gray-400 dark:border-gray-850"
			>
				{t('Showing latest state')} · {t('Time field')}: {meta?.fields?.time ?? '—'}
			</div>
		</section>

		<!-- Map -->
		<section class="flex min-h-0 flex-col gap-2 xl:col-span-4">
			<div class="h-72 min-h-0 overflow-hidden xl:h-auto xl:flex-1">
				<FlightMap {rows} {trajectories} {selectedIds} {focusId} {tileUrl} onToggle={toggle} />
			</div>

			<div
				class="rounded-2xl border border-gray-100 bg-white px-2.5 py-2 dark:border-gray-850 dark:bg-gray-900"
			>
				<div class="flex items-center justify-between gap-2">
					<div class="text-[11px] font-semibold text-gray-700 dark:text-gray-200">
						{t('Selected aircraft')}
						<span class="ms-1 font-normal text-gray-400">({selectedIds.length})</span>
					</div>
					<div class="flex items-center gap-1">
						{#if selectedIds.length}
							<button
								class="flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[10px] font-medium text-sky-600 transition hover:bg-sky-50 dark:text-sky-400 dark:hover:bg-sky-500/10"
								on:click={askAboutSelection}
							>
								<SparklesIcon className="size-3" strokeWidth="1.8" />
								{isPersian ? 'تحلیل انتخاب' : 'Analyse selection'}
							</button>
							<button
								class="rounded-md px-1.5 py-0.5 text-[10px] font-medium text-gray-500 transition hover:bg-gray-100 dark:text-gray-400 dark:hover:bg-gray-850"
								on:click={() => toggleAll(false)}
							>
								{t('Clear selection')}
							</button>
						{/if}
					</div>
				</div>

				{#if selectionNote}
					<div class="mt-1 text-[10px] text-amber-600 dark:text-amber-400">{selectionNote}</div>
				{/if}

				<div class="mt-1.5 flex flex-wrap gap-1">
					{#if !selectedIds.length}
						<p class="text-[11px] leading-5 text-gray-400">
							{t('Select one or more aircraft to draw their positions and trajectories.')}
						</p>
					{:else}
						{#each selectedIds as id (id)}
							{@const row = rows.find((item) => item.id === id)}
							<span
								class="inline-flex max-w-52 items-center gap-1 truncate rounded-md border border-gray-100 bg-gray-50/80 py-0.5 pe-1 ps-1.5 text-[10px] text-gray-600 dark:border-gray-850 dark:bg-gray-850/60 dark:text-gray-300"
							>
								<span class="size-1.5 rounded-full" style="background:{flightColor(id)}"></span>
								<span class="truncate font-medium">{row?.callsign ?? id}</span>
								{#if loadingTrajectories.includes(id)}
									<span class="text-gray-400">…</span>
								{:else if trajectories[id]}
									<span class="text-gray-400">{trajectories[id].count}</span>
								{/if}
								<button
									class="ms-0.5 text-gray-400 transition hover:text-gray-700 dark:hover:text-gray-100"
									on:click={() => removeSelected(id)}
									aria-label={t('Remove')}
								>
									<XMarkIcon className="size-3" strokeWidth="2" />
								</button>
							</span>
						{/each}
					{/if}
				</div>
			</div>
		</section>

		<!-- Chat -->
		<section
			class="flex min-h-[420px] flex-col overflow-hidden rounded-2xl border border-gray-100 bg-white xl:col-span-4 xl:min-h-0 dark:border-gray-850 dark:bg-gray-900"
		>
			<ChatSurface
				bind:this={chat}
				bind:modelId
				accent="sky"
				systemPrompt={systemPrompt()}
				emptyTitle={t('Flight Intelligence')}
				emptyDescription={isPersian
					? 'درباره هواپیماهای انتخاب‌شده یا کل بازه زمانی بپرس. پاسخ‌ها بر پایه داده محلی تو ساخته می‌شوند.'
					: 'Ask about the selected aircraft or the whole time window. Answers are grounded in your local data.'}
				placeholder={t('Ask about the selected aircraft…')}
				suggestions={isPersian
					? [
							'وضعیت کلی ناوگان در این بازه چگونه است؟',
							'کدام هواپیماها در حال کاهش ارتفاع هستند؟',
							'مسیر هواپیماهای انتخاب‌شده را خلاصه کن.',
							'الگوی ترافیک این بازه را تحلیل کن.'
						]
					: [
							'Summarise the traffic in this time window.',
							'Which aircraft are descending right now?',
							'Describe the routes of the selected aircraft.',
							'Are there any unusual patterns in this window?'
						]}
				{prepareContext}
			/>
		</section>
	</div>
</div>
