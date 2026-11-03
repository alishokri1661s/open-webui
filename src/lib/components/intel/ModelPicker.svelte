<script lang="ts">
	import { getContext } from 'svelte';
	import type { Readable } from 'svelte/store';
	import { models } from '$lib/stores';
	import { createIntelTranslator } from '$lib/intel/i18n';

	export let value = '';
	export let compact = false;

	const i18n = getContext<Readable<any>>('i18n');
	$: t = createIntelTranslator($i18n?.locale);

	$: available = ($models ?? []).filter((model: any) => model?.id);

	$: if (available.length && !available.some((model: any) => model.id === value)) {
		value = available[0].id;
	}
</script>

<div class="flex items-center gap-1.5 {compact ? '' : 'w-full'}">
	{#if !compact}
		<span class="text-[11px] font-medium uppercase tracking-wide text-gray-400 dark:text-gray-500">
			{t('Model')}
		</span>
	{/if}
	<select
		bind:value
		class="min-w-0 max-w-full flex-1 cursor-pointer truncate rounded-lg border border-gray-200/70 bg-transparent px-2 py-1 text-xs font-medium text-gray-700 outline-none transition hover:bg-gray-50 focus:border-gray-300 dark:border-gray-800 dark:text-gray-200 dark:hover:bg-gray-850"
		aria-label={t('Model')}
	>
		{#each available as model (model.id)}
			<option value={model.id}>{model.name ?? model.id}</option>
		{/each}
	</select>
</div>
