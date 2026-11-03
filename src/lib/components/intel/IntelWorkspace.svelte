<script lang="ts">
	import { getContext, onMount } from 'svelte';
	import type { Readable } from 'svelte/store';

	import { getIntelMeta, type IntelMeta } from '$lib/apis/intel';
	import { createIntelTranslator, formatNumber } from '$lib/intel/i18n';
	import { ACTIVE_TOPIC_ID, getTopicById, resolveTopic } from '$lib/intel/topic';

	import TopicChat from '$lib/components/intel/TopicChat.svelte';
	import FlightWorkspace from '$lib/components/intel/FlightWorkspace.svelte';
	import FileChat from '$lib/components/intel/FileChat.svelte';

	import GlobeAltIcon from '$lib/components/icons/GlobeAlt.svelte';
	import SparklesIcon from '$lib/components/icons/Sparkles.svelte';
	import MapIcon from '$lib/components/icons/Map.svelte';
	import DocumentIcon from '$lib/components/icons/Document.svelte';
	import HomeIcon from '$lib/components/icons/Home.svelte';
	import DatabaseIcon from '$lib/components/icons/Database.svelte';
	import InfoIcon from '$lib/components/icons/Info.svelte';
	import ArrowPathIcon from '$lib/components/icons/ArrowPath.svelte';
	import ArrowRightIcon from '$lib/components/icons/ArrowRight.svelte';
	import XMarkIcon from '$lib/components/icons/XMark.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	type Mode = 'home' | 'topic' | 'flights' | 'files';

	const i18n = getContext<Readable<any>>('i18n');
	$: t = createIntelTranslator($i18n?.locale);
	$: locale = $i18n?.locale;
	$: isPersian = (locale ?? '').toLowerCase().startsWith('fa');

	$: topic = resolveTopic(getTopicById(ACTIVE_TOPIC_ID), locale);

	const MODE_KEYS: Mode[] = ['topic', 'flights', 'files'];

	let mode: Mode = 'home';
	let meta: IntelMeta | null = null;
	let metaLoading = true;
	let metaError = '';
	let disabledMessage = '';
	let showSource = false;
	let modelId = '';
	let showDemoBanner = true;

	$: tabs = [
		{ id: 'topic' as Mode, label: t('Topic Expert'), icon: SparklesIcon },
		{ id: 'flights' as Mode, label: t('Flight Intelligence'), icon: MapIcon },
		{ id: 'files' as Mode, label: t('File Analyst'), icon: DocumentIcon }
	];

	const loadMeta = async (force = false) => {
		metaLoading = true;
		metaError = '';
		try {
			meta = await getIntelMeta(localStorage.token ?? '', force);
			disabledMessage = '';
		} catch (error) {
			metaError = error instanceof Error ? error.message : String(error);
			// The operator can switch the whole workspace off with INTEL_ENABLE=false.
			disabledMessage = /disabled/i.test(metaError) ? metaError : '';
		} finally {
			metaLoading = false;
		}
	};

	const selectMode = (next: Mode) => {
		mode = next;
		showSource = false;
		try {
			localStorage.setItem('intel.mode', next);
			const url = new URL(window.location.href);
			if (next === 'home') url.searchParams.delete('mode');
			else url.searchParams.set('mode', next);
			window.history.replaceState({}, '', url);
		} catch {
			// Storage/history may be unavailable in private mode.
		}
	};

	const status = () => {
		if (metaLoading) return { key: 'loading', label: t('Loading…'), tone: 'muted' };
		if (disabledMessage) return { key: 'disabled', label: t('Disabled'), tone: 'error' };
		if (metaError) return { key: 'error', label: t('Elasticsearch offline'), tone: 'error' };
		if (meta?.demo) return { key: 'demo', label: t('Demo dataset'), tone: 'warn' };
		if (meta?.elasticsearch?.connected)
			return { key: 'connected', label: t('Elasticsearch connected'), tone: 'ok' };
		return { key: 'error', label: t('Elasticsearch offline'), tone: 'error' };
	};

	$: statusInfo = status();
	$: statusTone =
		statusInfo.tone === 'ok'
			? 'bg-emerald-500'
			: statusInfo.tone === 'warn'
				? 'bg-amber-500'
				: statusInfo.tone === 'error'
					? 'bg-red-500'
					: 'bg-gray-300 dark:bg-gray-700';

	const cardAccent = 'from-sky-500/15 to-indigo-500/10 text-sky-600 dark:text-sky-400';

	onMount(() => {
		const params = new URLSearchParams(window.location.search);
		const requested = params.get('mode') as Mode | null;
		let saved: string | null = null;
		try {
			saved = localStorage.getItem('intel.mode');
			modelId = localStorage.getItem('intel.model') ?? '';
		} catch {
			// ignore
		}
		if (requested && MODE_KEYS.includes(requested)) {
			mode = requested;
		} else if (saved && MODE_KEYS.includes(saved as Mode)) {
			mode = saved as Mode;
		}
		void loadMeta();
	});

	$: if (modelId) {
		try {
			localStorage.setItem('intel.model', modelId);
		} catch {
			// ignore
		}
	}
</script>

<div class="flex h-full min-h-0 w-full flex-col overflow-hidden bg-gray-50/60 dark:bg-gray-950">
	<!-- Header -->
	<header
		class="relative z-30 shrink-0 border-b border-gray-100 bg-white/85 backdrop-blur dark:border-gray-850 dark:bg-gray-900/80"
	>
		<div class="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
			<button
				class="flex items-center gap-2 rounded-xl px-1 py-0.5 text-start transition hover:bg-gray-50 dark:hover:bg-gray-850/60"
				on:click={() => selectMode('home')}
				aria-label={t('Home')}
			>
				<span
					class="flex size-8 items-center justify-center rounded-xl bg-linear-to-br from-sky-500/20 to-indigo-500/10 text-sky-600 dark:text-sky-400"
				>
					<GlobeAltIcon className="size-4.5" strokeWidth="1.7" />
				</span>
				<span class="min-w-0">
					<span class="block truncate text-sm font-semibold text-gray-900 dark:text-gray-100">
						{t('Intelligence')}
					</span>
					<span class="block truncate text-[10px] text-gray-400">{t('Local-first workspace')}</span>
				</span>
			</button>

			<nav
				class="order-3 -mx-1 flex w-full items-center gap-0.5 overflow-x-auto px-1 sm:order-none sm:mx-0 sm:w-auto sm:flex-1 sm:px-0"
				aria-label={t('All workspaces')}
			>
				<button
					class="flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium transition {mode ===
					'home'
						? 'bg-gray-100 text-gray-900 dark:bg-gray-850 dark:text-white'
						: 'text-gray-500 hover:bg-gray-50 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-850/60 dark:hover:text-gray-200'}"
					on:click={() => selectMode('home')}
					title={t('Home')}
				>
					<HomeIcon className="size-3.5" strokeWidth="1.8" />
					<span class="hidden md:inline">{t('Home')}</span>
				</button>
				{#each tabs as tab (tab.id)}
					<button
						class="flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium transition {mode ===
						tab.id
							? 'bg-gray-100 text-gray-900 dark:bg-gray-850 dark:text-white'
							: 'text-gray-500 hover:bg-gray-50 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-850/60 dark:hover:text-gray-200'}"
						on:click={() => selectMode(tab.id)}
					>
						<svelte:component this={tab.icon} className="size-3.5" strokeWidth="1.8" />
						{tab.label}
					</button>
				{/each}
			</nav>

			<div class="ms-auto flex items-center gap-1.5">
				<button
					class="flex items-center gap-1.5 rounded-lg border border-gray-200/80 px-2 py-1 text-[11px] font-medium text-gray-600 transition hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850"
					on:click={() => (showSource = !showSource)}
				>
					{#if metaLoading}
						<Spinner className="size-3" />
					{:else}
						<span class="size-1.5 rounded-full {statusTone}"></span>
					{/if}
					<span class="hidden sm:inline">{statusInfo.label}</span>
					<DatabaseIcon className="size-3.5 text-gray-400" strokeWidth="1.8" />
				</button>

				<button
					class="flex size-7 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 dark:hover:bg-gray-850 dark:hover:text-gray-200"
					on:click={() => loadMeta(true)}
					title={t('Reconnect')}
					aria-label={t('Reconnect')}
				>
					<ArrowPathIcon
						className="size-3.5 {metaLoading ? 'animate-spin' : ''}"
						strokeWidth="1.8"
					/>
				</button>
			</div>
		</div>

		<!-- Data source popover -->
		{#if showSource}
			<div
				class="absolute end-3 top-full z-40 mt-1 w-[min(92vw,22rem)] rounded-xl border border-gray-100 bg-white p-3 shadow-lg dark:border-gray-800 dark:bg-gray-900"
			>
				<div class="mb-2 flex items-center justify-between">
					<span class="text-xs font-semibold text-gray-800 dark:text-gray-100"
						>{t('Data source')}</span
					>
					<button
						class="rounded-md p-0.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-850"
						on:click={() => (showSource = false)}
						aria-label={t('Close')}
					>
						<XMarkIcon className="size-3.5" strokeWidth="2" />
					</button>
				</div>

				<div class="space-y-1.5 text-[11px] text-gray-500 dark:text-gray-400">
					<div class="flex items-start justify-between gap-3">
						<span>{t('Index')}</span>
						<span class="truncate font-mono text-gray-700 dark:text-gray-200">
							{meta?.elasticsearch?.index ?? '—'}
						</span>
					</div>
					<div class="flex items-start justify-between gap-3">
						<span>{t('Documents')}</span>
						<span class="font-mono text-gray-700 dark:text-gray-200">
							{meta?.elasticsearch?.doc_count !== null &&
							meta?.elasticsearch?.doc_count !== undefined
								? formatNumber(meta.elasticsearch.doc_count, locale)
								: '—'}
						</span>
					</div>
					{#each Object.entries(meta?.fields ?? {}) as [key, value] (key)}
						{#if value}
							<div class="flex items-start justify-between gap-3">
								<span class="capitalize">{key}</span>
								<span class="truncate font-mono text-gray-700 dark:text-gray-200">{value}</span>
							</div>
						{/if}
					{/each}
					{#if meta?.elasticsearch?.error}
						<div
							class="mt-2 rounded-lg bg-red-50 px-2 py-1.5 text-[10px] text-red-600 dark:bg-red-500/10 dark:text-red-300"
						>
							{meta.elasticsearch.error}
						</div>
					{/if}
					{#if meta?.demo}
						<div
							class="mt-2 rounded-lg bg-amber-50 px-2 py-1.5 text-[10px] leading-4 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
						>
							{t(
								'Elasticsearch is not configured, so the workspace is showing a synthetic demo dataset. Set ELASTICSEARCH_URL to use your own index.'
							)}
						</div>
					{/if}
					<div class="mt-2 flex items-center gap-2">
						<button
							class="rounded-md border border-gray-200 px-2 py-1 text-[10px] font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850"
							on:click={() => loadMeta(true)}
						>
							{t('Retry connection')}
						</button>
					</div>
				</div>
			</div>
		{/if}
	</header>

	<!-- Banners -->
	{#if metaError}
		<div
			class="flex shrink-0 items-start gap-2 border-b border-red-100 bg-red-50 px-3 py-2 text-[11px] text-red-700 dark:border-red-500/20 dark:bg-red-500/10 dark:text-red-300"
		>
			<InfoIcon className="mt-0.5 size-3.5 shrink-0" strokeWidth="1.8" />
			<div class="min-w-0 flex-1">
				<span class="font-semibold">{t('Could not reach Elasticsearch.')} </span>{metaError}
			</div>
			<button class="font-semibold underline" on:click={() => loadMeta(true)}>{t('Retry')}</button>
		</div>
	{:else if meta?.demo && showDemoBanner}
		<div
			class="flex shrink-0 items-start gap-2 border-b border-amber-100 bg-amber-50 px-3 py-2 text-[11px] text-amber-800 dark:border-amber-500/20 dark:bg-amber-500/10 dark:text-amber-200"
		>
			<InfoIcon className="mt-0.5 size-3.5 shrink-0" strokeWidth="1.8" />
			<div class="min-w-0 flex-1">
				{t(
					'Elasticsearch is not configured, so the workspace is showing a synthetic demo dataset. Set ELASTICSEARCH_URL to use your own index.'
				)}
			</div>
			<button
				class="rounded-md p-0.5 text-amber-600 transition hover:bg-amber-100 dark:text-amber-300 dark:hover:bg-amber-500/20"
				on:click={() => (showDemoBanner = false)}
				aria-label={t('Dismiss')}
			>
				<XMarkIcon className="size-3.5" strokeWidth="2" />
			</button>
		</div>
	{/if}

	<!-- Content -->
	<main class="min-h-0 flex-1 overflow-y-auto p-3">
		{#if disabledMessage}
			<div class="mx-auto flex h-full max-w-lg flex-col items-center justify-center text-center">
				<div
					class="mb-3 flex size-12 items-center justify-center rounded-2xl bg-gray-100 text-gray-400 dark:bg-gray-850"
				>
					<DatabaseIcon className="size-6" strokeWidth="1.6" />
				</div>
				<h2 class="text-base font-semibold text-gray-900 dark:text-gray-100">
					{t('Intelligence workspace')}
				</h2>
				<p class="mt-1 text-xs leading-5 text-gray-500 dark:text-gray-400">
					{t(
						'This workspace is disabled on this server. Ask an administrator to set INTEL_ENABLE=true to switch it on.'
					)}
				</p>
				<p class="mt-2 font-mono text-[10px] text-gray-400">{disabledMessage}</p>
				<button
					class="mt-3 rounded-lg border border-gray-200 px-3 py-1.5 text-[11px] font-medium text-gray-600 hover:bg-gray-50 dark:border-gray-800 dark:text-gray-300 dark:hover:bg-gray-850"
					on:click={() => loadMeta(true)}
				>
					{t('Retry connection')}
				</button>
			</div>
		{:else}
			{#if mode === 'home'}
				<div class="mx-auto flex min-h-full w-full max-w-5xl flex-col justify-center py-4">
					<div class="mb-6 text-center">
						<div
							class="mx-auto mb-3 flex size-12 items-center justify-center rounded-2xl bg-linear-to-br from-sky-500/20 to-indigo-500/10 text-sky-600 dark:text-sky-400"
						>
							<GlobeAltIcon className="size-6" strokeWidth="1.6" />
						</div>
						<h1 class="text-xl font-semibold text-gray-900 dark:text-gray-50">
							{t('Choose a workspace')}
						</h1>
						<p class="mx-auto mt-1 max-w-lg text-xs leading-5 text-gray-500 dark:text-gray-400">
							{t('Pick the mode that matches your question. You can switch at any time.')}
						</p>
					</div>

					<div class="grid grid-cols-1 gap-3 md:grid-cols-3">
						<!-- Topic expert -->
						<button
							class="group flex h-full flex-col rounded-2xl border border-gray-100 bg-white p-4 text-start transition hover:-translate-y-0.5 hover:border-sky-200 hover:shadow-sm dark:border-gray-850 dark:bg-gray-900 dark:hover:border-sky-500/40"
							on:click={() => selectMode('topic')}
						>
							<div class="mb-3 flex items-center justify-between">
								<span
									class="flex size-9 items-center justify-center rounded-xl bg-linear-to-br {cardAccent}"
								>
									<SparklesIcon className="size-4.5" strokeWidth="1.7" />
								</span>
								<span
									class="rounded-full bg-gray-100 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-gray-500 dark:bg-gray-850 dark:text-gray-400"
								>
									{topic.badge}
								</span>
							</div>
							<h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
								{t('Topic Expert')}
							</h2>
							<p class="mt-1 text-[11px] leading-5 text-gray-500 dark:text-gray-400">
								{topic.tagline}
							</p>
							<ul class="mt-3 space-y-1 text-[11px] leading-5 text-gray-500 dark:text-gray-400">
								<li>· {topic.name}</li>
								<li>
									· {isPersian
										? 'پرامپت تخصصی، قابل ویرایش در کد'
										: 'Purpose-built prompt, editable as code'}
								</li>
								<li>
									· {isPersian
										? 'کاملاً آفلاین با مدل محلی'
										: 'Fully offline with your local model'}
								</li>
							</ul>
							<span
								class="mt-3 inline-flex items-center gap-1 text-[11px] font-semibold text-sky-600 dark:text-sky-400"
							>
								{t('Open')}
								<ArrowRightIcon
									className="size-3 transition group-hover:translate-x-0.5"
									strokeWidth="2"
								/>
							</span>
						</button>

						<!-- Flight intelligence -->
						<button
							class="group flex h-full flex-col rounded-2xl border border-gray-100 bg-white p-4 text-start transition hover:-translate-y-0.5 hover:border-emerald-200 hover:shadow-sm dark:border-gray-850 dark:bg-gray-900 dark:hover:border-emerald-500/40"
							on:click={() => selectMode('flights')}
						>
							<div class="mb-3 flex items-center justify-between">
								<span
									class="flex size-9 items-center justify-center rounded-xl bg-linear-to-br from-emerald-500/15 to-teal-500/10 text-emerald-600 dark:text-emerald-400"
								>
									<MapIcon className="size-4.5" strokeWidth="1.7" />
								</span>
								<span
									class="rounded-full bg-emerald-100 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-emerald-600 dark:bg-emerald-500/15 dark:text-emerald-300"
								>
									{t('Elasticsearch')}
								</span>
							</div>
							<h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
								{t('Flight Intelligence')}
							</h2>
							<p class="mt-1 text-[11px] leading-5 text-gray-500 dark:text-gray-400">
								{isPersian
									? 'جدول آخرین وضعیت هواپیماها، فیلتر زمانی، نقشه مسیرها و چت درباره اهداف انتخاب‌شده.'
									: 'Latest state per aircraft, time filtering, trajectory map and chat about the selected targets.'}
							</p>
							<ul class="mt-3 space-y-1 text-[11px] leading-5 text-gray-500 dark:text-gray-400">
								<li>· {isPersian ? 'جدول + فیلتر زمانی' : 'Table + time range filters'}</li>
								<li>· {isPersian ? 'نقشه آفلاین با مسیر' : 'Offline map with trajectories'}</li>
								<li>· {isPersian ? 'چت مبتنی بر انتخاب' : 'Selection-aware chat'}</li>
							</ul>
							<span
								class="mt-3 inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-600 dark:text-emerald-400"
							>
								{t('Open')}
								<ArrowRightIcon
									className="size-3 transition group-hover:translate-x-0.5"
									strokeWidth="2"
								/>
							</span>
						</button>

						<!-- File analyst -->
						<button
							class="group flex h-full flex-col rounded-2xl border border-gray-100 bg-white p-4 text-start transition hover:-translate-y-0.5 hover:border-amber-200 hover:shadow-sm dark:border-gray-850 dark:bg-gray-900 dark:hover:border-amber-500/40"
							on:click={() => selectMode('files')}
						>
							<div class="mb-3 flex items-center justify-between">
								<span
									class="flex size-9 items-center justify-center rounded-xl bg-linear-to-br from-amber-500/15 to-orange-500/10 text-amber-600 dark:text-amber-400"
								>
									<DocumentIcon className="size-4.5" strokeWidth="1.7" />
								</span>
								<span
									class="rounded-full bg-gray-100 px-2 py-0.5 text-[9px] font-semibold uppercase tracking-wide text-gray-500 dark:bg-gray-850 dark:text-gray-400"
								>
									RAG
								</span>
							</div>
							<h2 class="text-sm font-semibold text-gray-900 dark:text-gray-100">
								{t('File Analyst')}
							</h2>
							<p class="mt-1 text-[11px] leading-5 text-gray-500 dark:text-gray-400">
								{isPersian
									? 'فایل آپلود کن و از محتوای آن پرسش کن؛ پاسخ‌ها به بخش‌های مشخص سند مستند می‌شوند.'
									: 'Upload files and ask about their content; answers cite the exact passages they rely on.'}
							</p>
							<ul class="mt-3 space-y-1 text-[11px] leading-5 text-gray-500 dark:text-gray-400">
								<li>· {isPersian ? 'PDF، DOCX، CSV، متن' : 'PDF, DOCX, CSV, text'}</li>
								<li>· {isPersian ? 'بازیابی محلی بخش‌ها' : 'Local passage retrieval'}</li>
								<li>· {isPersian ? 'پاسخ مستند با ارجاع' : 'Cited, grounded answers'}</li>
							</ul>
							<span
								class="mt-3 inline-flex items-center gap-1 text-[11px] font-semibold text-amber-600 dark:text-amber-400"
							>
								{t('Open')}
								<ArrowRightIcon
									className="size-3 transition group-hover:translate-x-0.5"
									strokeWidth="2"
								/>
							</span>
						</button>
					</div>

					<div
						class="mt-4 flex flex-wrap items-center justify-between gap-2 text-[10px] text-gray-400"
					>
						<span class="inline-flex items-center gap-1.5">
							<span class="size-1.5 rounded-full {statusTone}"></span>
							{statusInfo.label}
							{#if meta?.elasticsearch?.index}
								· <span class="font-mono">{meta.elasticsearch.index}</span>
							{/if}
						</span>
						<span
							>{t(
								'Everything runs on your own machine — models, documents and flight data stay offline.'
							)}</span
						>
					</div>
				</div>
			{/if}

			<!-- The three workspaces stay mounted so switching tabs (or going home) never
		     loses a conversation or a selection. -->
			<div class="h-full" class:hidden={mode !== 'topic'}>
				<TopicChat bind:modelId {meta} />
			</div>
			<div class="h-full" class:hidden={mode !== 'flights'}>
				<FlightWorkspace bind:modelId {meta} />
			</div>
			<div class="h-full" class:hidden={mode !== 'files'}>
				<FileChat bind:modelId />
			</div>
		{/if}
	</main>
</div>
