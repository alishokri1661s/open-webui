<script lang="ts">
	import { getContext } from 'svelte';
	import type { Readable } from 'svelte/store';

	import type { IntelMeta } from '$lib/apis/intel';
	import { createIntelTranslator } from '$lib/intel/i18n';
	import { ACTIVE_TOPIC_ID, getTopicById, resolveTopic } from '$lib/intel/topic';
	import ChatSurface from '$lib/components/intel/ChatSurface.svelte';
	import SparklesIcon from '$lib/components/icons/Sparkles.svelte';

	export let modelId = '';
	export let meta: IntelMeta | null = null;

	const i18n = getContext<Readable<any>>('i18n');
	$: t = createIntelTranslator($i18n?.locale);
	$: isPersian = ($i18n?.locale ?? '').toLowerCase().startsWith('fa');

	$: topic = resolveTopic(getTopicById(ACTIVE_TOPIC_ID), $i18n?.locale);
	$: topicName = meta?.topic?.name?.trim() || topic.name;
	$: systemPrompt = meta?.topic?.prompt?.trim() || topic.systemPrompt;
	$: suggestions = meta?.topic?.suggestions?.length ? meta.topic.suggestions : topic.suggestions;
</script>

<div class="mx-auto flex h-full min-h-0 w-full max-w-4xl flex-col gap-3">
	<div
		class="flex flex-wrap items-start justify-between gap-3 rounded-2xl border border-gray-100 bg-white p-3.5 dark:border-gray-850 dark:bg-gray-900"
	>
		<div class="flex min-w-0 items-start gap-3">
			<div
				class="flex size-10 shrink-0 items-center justify-center rounded-xl bg-linear-to-br from-sky-500/15 to-indigo-500/10 text-sky-600 dark:text-sky-400"
			>
				{#if topic.badge}
					<span class="text-[11px] font-bold tracking-wide">{topic.badge}</span>
				{:else}
					<SparklesIcon className="size-5" strokeWidth="1.7" />
				{/if}
			</div>
			<div class="min-w-0">
				<h2 class="truncate text-sm font-semibold text-gray-900 dark:text-gray-100">{topicName}</h2>
				<p class="mt-0.5 max-w-2xl text-xs leading-5 text-gray-500 dark:text-gray-400">
					{topic.description}
				</p>
			</div>
		</div>

		<div class="flex flex-col items-end gap-1">
			<span
				class="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-medium text-gray-500 dark:bg-gray-850 dark:text-gray-400"
			>
				{t('Local-first workspace')}
			</span>
			{#if meta && !meta.demo && meta.elasticsearch.connected}
				<a
					class="text-[10px] font-medium text-sky-600 hover:underline dark:text-sky-400"
					href="/intel?mode=flights"
				>
					{isPersian ? 'داده پروازها هم در دسترس است' : 'Flight data is available too'}
				</a>
			{/if}
		</div>
	</div>

	<div
		class="min-h-0 flex-1 overflow-hidden rounded-2xl border border-gray-100 bg-white dark:border-gray-850 dark:bg-gray-900"
	>
		<ChatSurface
			bind:modelId
			accent="sky"
			{systemPrompt}
			{suggestions}
			emptyTitle={topicName}
			emptyDescription={topic.tagline}
			placeholder={t('Ask a question…')}
		/>
	</div>
</div>
