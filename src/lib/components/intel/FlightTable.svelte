<script lang="ts">
	import { getContext } from 'svelte';
	import type { Readable } from 'svelte/store';
	import type { IntelFlightRow } from '$lib/apis/intel';
	import { createIntelTranslator, formatDateTime, formatNumber } from '$lib/intel/i18n';
	import { flightColor } from '$lib/intel/colors';

	export let rows: IntelFlightRow[] = [];
	export let selectedIds: string[] = [];
	export let loading = false;
	export let onToggle: ((id: string) => void) | null = null;
	export let onToggleAll: ((select: boolean) => void) | null = null;
	export let onFocus: ((id: string) => void) | null = null;

	const i18n = getContext<Readable<any>>('i18n');
	$: t = createIntelTranslator($i18n?.locale);
	$: locale = $i18n?.locale;

	$: allSelected = rows.length > 0 && rows.every((row) => selectedIds.includes(row.id));

	const formatAltitude = (value: number | null) =>
		value === null || value === undefined ? '—' : formatNumber(Math.round(value), locale);
</script>

<div class="flex min-h-0 flex-col">
	<div class="scrollbar-hidden min-h-0 flex-1 overflow-auto">
		<table class="w-full table-fixed border-collapse text-start">
			<thead
				class="sticky top-0 z-10 bg-white text-[10px] uppercase tracking-wide text-gray-400 dark:bg-gray-900"
			>
				<tr class="border-b border-gray-100 dark:border-gray-850">
					<th class="w-8 px-2 py-1.5">
						<input
							type="checkbox"
							class="size-3.5 cursor-pointer accent-sky-500 align-middle"
							checked={allSelected}
							aria-label={t('Select all')}
							on:change={() => onToggleAll?.(!allSelected)}
						/>
					</th>
					<th class="px-1.5 py-1.5 text-start font-medium">{t('Callsign')}</th>
					<th class="hidden w-16 px-1.5 py-1.5 text-end font-medium sm:table-cell"
						>{t('Altitude')}</th
					>
					<th class="hidden w-14 px-1.5 py-1.5 text-end font-medium lg:table-cell">{t('Speed')}</th>
					<th class="w-[74px] px-1.5 py-1.5 text-end font-medium">{t('Last seen')}</th>
				</tr>
			</thead>
			<tbody>
				{#if loading && !rows.length}
					{#each Array(6) as _, index (index)}
						<tr class="border-b border-gray-50 dark:border-gray-850/60">
							<td class="px-2 py-2.5" colspan="5">
								<div class="h-3 w-full animate-pulse rounded bg-gray-100 dark:bg-gray-850"></div>
							</td>
						</tr>
					{/each}
				{:else if !rows.length}
					<tr>
						<td colspan="5" class="px-3 py-8 text-center text-xs text-gray-400">
							{t('No aircraft in this time window.')}
						</td>
					</tr>
				{:else}
					{#each rows as row (row.id)}
						{@const selected = selectedIds.includes(row.id)}
						<tr
							class="group cursor-pointer border-b border-gray-50 text-xs transition-colors last:border-0 dark:border-gray-850/60 {selected
								? 'bg-sky-50/70 dark:bg-sky-500/10'
								: 'hover:bg-gray-50/80 dark:hover:bg-gray-850/50'}"
							on:click={() => onToggle?.(row.id)}
							on:dblclick={() => onFocus?.(row.id)}
							title={t('Select one or more aircraft to draw their positions and trajectories.')}
						>
							<td class="px-2 py-1.5" on:click|stopPropagation on:keydown|stopPropagation>
								<input
									type="checkbox"
									class="size-3.5 cursor-pointer accent-sky-500 align-middle"
									checked={selected}
									aria-label={row.callsign}
									on:change={() => onToggle?.(row.id)}
								/>
							</td>
							<td class="px-1.5 py-1.5">
								<div class="flex min-w-0 items-center gap-1.5">
									<span
										class="size-1.5 shrink-0 rounded-full"
										style="background:{flightColor(row.id)}; opacity:{selected ? 1 : 0.45}"
									></span>
									<div class="min-w-0">
										<div class="truncate font-semibold text-gray-800 dark:text-gray-100">
											{row.callsign}
										</div>
										<div class="truncate text-[10px] text-gray-400">
											{#if row.origin || row.destination}
												{row.origin ?? '?'} → {row.destination ?? '?'}
											{:else}
												{row.id}
											{/if}
											{#if row.status}
												· {row.status}
											{/if}
										</div>
									</div>
								</div>
							</td>
							<td
								class="hidden px-1.5 py-1.5 text-end tabular-nums text-gray-600 sm:table-cell dark:text-gray-300"
							>
								{formatAltitude(row.altitude)}
							</td>
							<td
								class="hidden px-1.5 py-1.5 text-end tabular-nums text-gray-600 lg:table-cell dark:text-gray-300"
							>
								{row.speed === null || row.speed === undefined
									? '—'
									: formatNumber(Math.round(row.speed), locale)}
							</td>
							<td class="px-1.5 py-1.5 text-end text-[10px] tabular-nums text-gray-400">
								{formatDateTime(row.time, locale)}
							</td>
						</tr>
					{/each}
				{/if}
			</tbody>
		</table>
	</div>
</div>
