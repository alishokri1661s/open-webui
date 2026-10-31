<script lang="ts">
	import { getContext, onDestroy, tick } from 'svelte';
	import type { Readable } from 'svelte/store';
	import { v4 as uuidv4 } from 'uuid';

	import { chatCompletion } from '$lib/apis/openai';
	import { createOpenAITextStream } from '$lib/apis/streaming';
	import Markdown from '$lib/components/chat/Messages/Markdown.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';
	import ModelPicker from '$lib/components/intel/ModelPicker.svelte';
	import { createIntelTranslator } from '$lib/intel/i18n';
	import { composeUserMessage, type Citation, type PreparedContext } from '$lib/intel/context';

	import ArrowUpIcon from '$lib/components/icons/ArrowUpCircle.svelte';
	import CopyIcon from '$lib/components/icons/Clipboard.svelte';
	import RefreshIcon from '$lib/components/icons/Refresh.svelte';
	import TrashIcon from '$lib/components/icons/Trash.svelte';
	import SparklesIcon from '$lib/components/icons/Sparkles.svelte';
	import DocumentIcon from '$lib/components/icons/Document.svelte';

	export let modelId = '';
	export let systemPrompt = '';
	export let suggestions: string[] = [];
	export let placeholder = 'Ask a question…';
	export let emptyTitle = '';
	export let emptyDescription = '';
	export let disabled = false;
	export let disabledReason = '';
	export let prepareContext: ((question: string) => Promise<PreparedContext>) | null = null;
	export let accent = 'sky';

	type ChatMessage = {
		id: string;
		role: 'user' | 'assistant';
		content: string;
		citations?: Citation[];
		error?: string;
		streaming?: boolean;
	};

	const i18n = getContext<Readable<any>>('i18n');
	$: t = createIntelTranslator($i18n?.locale);
	$: isPersian = ($i18n?.locale ?? '').toLowerCase().startsWith('fa');

	let messages: ChatMessage[] = [];
	let prompt = '';
	let busy = false;
	let preparing = false;
	let inputEl: HTMLTextAreaElement | null = null;
	let scrollEl: HTMLDivElement | null = null;
	let controller: AbortController | null = null;
	let stoppedByUser = false;
	let copiedId = '';

	const accentRing: Record<string, string> = {
		sky: 'from-sky-500/15 to-indigo-500/10 text-sky-600 dark:text-sky-400',
		amber: 'from-amber-500/15 to-orange-500/10 text-amber-600 dark:text-amber-400',
		emerald: 'from-emerald-500/15 to-teal-500/10 text-emerald-600 dark:text-emerald-400'
	};

	const scrollToBottom = async (force = false) => {
		await tick();
		if (!scrollEl) return;
		const distance = scrollEl.scrollHeight - scrollEl.scrollTop - scrollEl.clientHeight;
		if (force || distance < 220) scrollEl.scrollTop = scrollEl.scrollHeight;
	};

	const updateMessage = (id: string, patch: Partial<ChatMessage>) => {
		messages = messages.map((message) => (message.id === id ? { ...message, ...patch } : message));
	};

	export function reset() {
		controller?.abort();
		messages = [];
		prompt = '';
		busy = false;
		preparing = false;
	}

	export function focus() {
		inputEl?.focus();
	}

	/** Ask a question programmatically (used by the map "analyse selection" button). */
	export function ask(question: string) {
		if (!question?.trim()) return;
		prompt = question;
		void send();
	}

	const resize = () => {
		if (!inputEl) return;
		inputEl.style.height = 'auto';
		inputEl.style.height = `${Math.min(160, inputEl.scrollHeight)}px`;
	};

	const streamAnswer = async (assistantId: string, userContent: string) => {
		const token = localStorage.token ?? '';
		// Everything before the current (user, assistant) pair is conversation history.
		const history = messages
			.slice(0, -2)
			.filter((message) => message.content)
			.slice(-8)
			.map((message) => ({ role: message.role, content: message.content }));

		const body = {
			model: modelId,
			stream: true,
			messages: [
				{ role: 'system', content: systemPrompt },
				...history,
				{ role: 'user', content: userContent }
			]
		};

		const [response, abortController] = await chatCompletion(token, body);
		controller = abortController;
		if (!response) throw new Error('No response from the model');
		if (!response.ok) {
			let detail = `HTTP ${response.status}`;
			try {
				const payload = await response.json();
				detail = payload?.detail || payload?.error?.message || payload?.error || detail;
			} catch {
				// ignore
			}
			throw new Error(String(detail));
		}

		const contentType = response.headers.get('content-type') ?? '';
		let content = '';

		if (contentType.includes('application/json')) {
			const payload = await response.json();
			content = payload?.choices?.[0]?.message?.content ?? '';
			updateMessage(assistantId, { content, streaming: false });
			return content;
		}

		if (!response.body) throw new Error('The model returned an empty stream');
		const stream = await createOpenAITextStream(response.body, false);

		for await (const update of stream) {
			if (update.error) {
				throw new Error(
					typeof update.error === 'string' ? update.error : 'The model returned an error'
				);
			}
			if (update.done) break;
			if (update.value) {
				content += update.value;
				updateMessage(assistantId, { content });
				void scrollToBottom();
			}
		}

		updateMessage(assistantId, { content, streaming: false });
		return content;
	};

	const send = async () => {
		const question = prompt.trim();
		if (!question || busy || preparing || disabled) return;
		if (!modelId) return;

		prompt = '';
		busy = true;
		stoppedByUser = false;
		await tick();
		resize();

		const userMessageId = uuidv4();
		const assistantId = uuidv4();
		messages = [
			...messages,
			{ id: userMessageId, role: 'user', content: question },
			{ id: assistantId, role: 'assistant', content: '', streaming: true }
		];
		scrollToBottom(true);

		let prepared: PreparedContext = { context: '', citations: [] };
		try {
			if (prepareContext) {
				preparing = true;
				prepared = await prepareContext(question);
				preparing = false;
				updateMessage(userMessageId, { content: question, citations: prepared.citations });
			}
		} catch (error) {
			preparing = false;
			updateMessage(assistantId, {
				content: '',
				streaming: false,
				error: error instanceof Error ? error.message : String(error)
			});
			busy = false;
			return;
		}

		// The retrieval context is injected into the model turn only; the visible
		// bubble keeps the clean question and shows the citations instead.
		const contextual = composeUserMessage(question, prepared.context);

		try {
			await streamAnswer(assistantId, contextual);
		} catch (error) {
			if (stoppedByUser) {
				updateMessage(assistantId, { streaming: false });
			} else {
				const message = error instanceof Error ? error.message : String(error);
				updateMessage(assistantId, {
					streaming: false,
					error: message
				});
			}
		} finally {
			// Restore the clean question in the visible transcript.
			updateMessage(userMessageId, { content: question, citations: prepared.citations });
			busy = false;
			preparing = false;
			controller = null;
			scrollToBottom();
			inputEl?.focus();
		}
	};

	const stop = () => {
		stoppedByUser = true;
		controller?.abort();
		busy = false;
	};

	const retry = async () => {
		if (busy) return;
		let lastUserIndex = -1;
		for (let index = messages.length - 1; index >= 0; index -= 1) {
			if (messages[index].role === 'user') {
				lastUserIndex = index;
				break;
			}
		}
		if (lastUserIndex === -1) return;
		const question = messages[lastUserIndex].content;
		messages = messages.slice(0, lastUserIndex);
		prompt = question;
		await tick();
		await send();
	};

	const copy = async (message: ChatMessage) => {
		try {
			await navigator.clipboard.writeText(message.content);
			copiedId = message.id;
			setTimeout(() => (copiedId = ''), 1500);
		} catch {
			// clipboard may be unavailable in insecure contexts
		}
	};

	const onKeyDown = (event: KeyboardEvent) => {
		if (event.key === 'Enter' && !event.shiftKey) {
			event.preventDefault();
			send();
		}
	};

	onDestroy(() => controller?.abort());
</script>

<div class="flex h-full min-h-0 flex-col">
	<!-- Header -->
	<div
		class="flex flex-wrap items-center justify-between gap-2 border-b border-gray-100 px-3 py-2 dark:border-gray-850"
	>
		<div class="flex min-w-0 items-center gap-2">
			<div
				class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-linear-to-br {accentRing[
					accent
				] ?? accentRing.sky}"
			>
				<SparklesIcon className="size-4" strokeWidth="1.8" />
			</div>
			<div class="min-w-0">
				<div class="truncate text-sm font-medium text-gray-900 dark:text-gray-100">
					{emptyTitle || t('Assistant')}
				</div>
				{#if preparing}
					<div class="text-[11px] text-gray-400">{t('Preparing context…')}</div>
				{:else if busy}
					<div class="text-[11px] text-gray-400">{t('Answering…')}</div>
				{/if}
			</div>
		</div>

		<div class="flex items-center gap-1.5">
			<ModelPicker bind:value={modelId} compact />
			{#if messages.length}
				<button
					class="flex size-7 items-center justify-center rounded-lg text-gray-400 transition hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-850 dark:hover:text-gray-200"
					title={t('Clear conversation')}
					aria-label={t('Clear conversation')}
					on:click={reset}
				>
					<TrashIcon className="size-4" strokeWidth="1.6" />
				</button>
			{/if}
		</div>
	</div>

	<!-- Messages -->
	<div bind:this={scrollEl} class="scrollbar-hidden min-h-0 flex-1 overflow-y-auto px-3 py-3">
		{#if !messages.length}
			<div class="flex h-full flex-col items-center justify-center px-2 text-center">
				<div
					class="mb-3 flex size-12 items-center justify-center rounded-2xl bg-linear-to-br {accentRing[
						accent
					] ?? accentRing.sky}"
				>
					<SparklesIcon className="size-6" strokeWidth="1.6" />
				</div>
				{#if emptyDescription}
					<p class="max-w-md text-sm leading-6 text-gray-500 dark:text-gray-400">
						{emptyDescription}
					</p>
				{/if}

				{#if suggestions.length}
					<div class="mt-4 flex w-full max-w-md flex-col gap-1.5">
						{#each suggestions as suggestion, index (index)}
							<button
								class="rounded-xl border border-gray-100 bg-gray-50/60 px-3 py-2 text-start text-xs leading-5 text-gray-600 transition hover:border-gray-200 hover:bg-gray-100/70 dark:border-gray-850 dark:bg-gray-900/60 dark:text-gray-300 dark:hover:border-gray-800 dark:hover:bg-gray-850"
								on:click={() => {
									prompt = suggestion;
									send();
								}}
							>
								{suggestion}
							</button>
						{/each}
					</div>
				{/if}
			</div>
		{:else}
			<div class="flex flex-col gap-4">
				{#each messages as message (message.id)}
					<div class="flex flex-col gap-1.5">
						<div
							class="flex items-center gap-2 text-[11px] font-medium uppercase tracking-wide text-gray-400"
						>
							<span>{message.role === 'user' ? t('You') : t('Assistant')}</span>
							{#if message.streaming}
								<Spinner className="size-3" />
							{/if}
						</div>

						{#if message.role === 'user'}
							<div
								class="whitespace-pre-wrap wrap-break-word rounded-xl bg-gray-100 px-3 py-2 text-sm leading-6 text-gray-800 dark:bg-gray-850 dark:text-gray-100"
							>
								{message.content}
							</div>
						{:else}
							<div
								class="group relative rounded-xl border border-gray-100 px-3 py-2 dark:border-gray-850"
							>
								{#if message.content}
									<Markdown
										id={message.id}
										chatId="intel"
										messageId={message.id}
										content={message.content}
										done={!message.streaming}
										topPadding={false}
									/>
								{:else if message.streaming}
									<div class="flex items-center gap-2 py-1 text-xs text-gray-400">
										<Spinner className="size-3" />
										{t('Thinking…')}
									</div>
								{/if}

								{#if message.error}
									<div class="mt-1 text-xs text-red-500">
										{message.error}
									</div>
								{/if}

								{#if message.citations?.length}
									<div
										class="mt-2 flex flex-wrap items-center gap-1.5 border-t border-gray-100 pt-2 dark:border-gray-850"
									>
										<span
											class="inline-flex items-center gap-1 text-[10px] font-medium uppercase tracking-wide text-gray-400"
										>
											<DocumentIcon className="size-3" strokeWidth="1.8" />
											{t('Sources')}
										</span>
										{#each message.citations.slice(0, 8) as citation, index (index)}
											<span
												class="max-w-40 truncate rounded-md bg-gray-100 px-1.5 py-0.5 text-[10px] text-gray-500 dark:bg-gray-850 dark:text-gray-400"
												title={`${citation.label}${citation.detail ? ` · ${citation.detail}` : ''}`}
											>
												{citation.label}{citation.detail ? ` · ${citation.detail}` : ''}
											</span>
										{/each}
									</div>
								{/if}

								{#if !message.streaming && message.content}
									<div
										class="mt-1 flex items-center gap-1 opacity-0 transition group-hover:opacity-100"
									>
										<button
											class="flex items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-850"
											on:click={() => copy(message)}
										>
											<CopyIcon className="size-3" strokeWidth="1.8" />
											{copiedId === message.id ? t('Copied') : t('Copy')}
										</button>
									</div>
								{/if}
							</div>
						{/if}
					</div>
				{/each}

				{#if !busy && messages[messages.length - 1]?.error}
					<button
						class="ms-auto flex items-center gap-1.5 rounded-lg border border-gray-200 px-2 py-1 text-xs text-gray-500 transition hover:bg-gray-50 dark:border-gray-800 dark:hover:bg-gray-850"
						on:click={retry}
					>
						<RefreshIcon className="size-3.5" strokeWidth="1.8" />
						{t('Retry')}
					</button>
				{/if}
			</div>
		{/if}
	</div>

	<!-- Composer -->
	<div class="border-t border-gray-100 px-3 py-2.5 dark:border-gray-850">
		{#if disabled}
			<div
				class="rounded-xl bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
			>
				{disabledReason}
			</div>
		{:else}
			<div
				class="flex items-end gap-2 rounded-xl border border-gray-200/80 bg-white px-2 py-1.5 transition focus-within:border-gray-300 dark:border-gray-800 dark:bg-gray-900 dark:focus-within:border-gray-700"
			>
				<textarea
					bind:this={inputEl}
					bind:value={prompt}
					on:input={resize}
					on:keydown={onKeyDown}
					rows="1"
					dir={isPersian ? 'rtl' : 'ltr'}
					{placeholder}
					class="scrollbar-hidden max-h-40 min-h-6 flex-1 resize-none bg-transparent py-1 text-sm leading-6 outline-none placeholder:text-gray-400 dark:text-gray-100"
				></textarea>

				{#if busy}
					<button
						class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gray-900 text-white transition hover:bg-gray-700 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-200"
						title={t('Stop')}
						aria-label={t('Stop')}
						on:click={stop}
					>
						<span class="block size-2.5 rounded-[2px] bg-current"></span>
					</button>
				{:else}
					<button
						class="flex size-7 shrink-0 items-center justify-center rounded-lg bg-gray-900 text-white transition disabled:cursor-not-allowed disabled:opacity-30 hover:bg-gray-700 dark:bg-white dark:text-gray-900 dark:hover:bg-gray-200"
						title={t('Send')}
						aria-label={t('Send')}
						disabled={!prompt.trim() || !modelId}
						on:click={send}
					>
						<ArrowUpIcon className="size-4" strokeWidth="2" />
					</button>
				{/if}
			</div>
			{#if !modelId}
				<div class="mt-1.5 text-[11px] text-red-500">{t('No local model is available yet.')}</div>
			{/if}
		{/if}
	</div>
</div>
