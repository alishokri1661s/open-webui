<script lang="ts">
	import { getContext } from 'svelte';
	import type { Readable } from 'svelte/store';
	import { v4 as uuidv4 } from 'uuid';

	import { deleteFileById, getFileById, getFileIndexedText, uploadFile } from '$lib/apis/files';
	import { user } from '$lib/stores';
	import { buildFileContext } from '$lib/intel/context';
	import { createIntelTranslator, formatNumber } from '$lib/intel/i18n';

	import ChatSurface from '$lib/components/intel/ChatSurface.svelte';

	import CloudArrowUpIcon from '$lib/components/icons/CloudArrowUp.svelte';
	import DocumentIcon from '$lib/components/icons/Document.svelte';
	import XMarkIcon from '$lib/components/icons/XMark.svelte';
	import CheckCircleIcon from '$lib/components/icons/CheckCircle.svelte';
	import InfoIcon from '$lib/components/icons/Info.svelte';
	import Spinner from '$lib/components/common/Spinner.svelte';

	export let modelId = '';

	type DocStatus = 'uploading' | 'processing' | 'ready' | 'error';

	type UploadedDoc = {
		key: string;
		id: string | null;
		name: string;
		size: number;
		status: DocStatus;
		text: string;
		error?: string;
	};

	const i18n = getContext<Readable<any>>('i18n');
	$: t = createIntelTranslator($i18n?.locale);
	$: locale = $i18n?.locale;
	$: isPersian = (locale ?? '').toLowerCase().startsWith('fa');
	$: canUpload =
		($user?.role === 'admin' || ($user?.permissions?.chat?.file_upload ?? true)) ?? true;

	let docs: UploadedDoc[] = [];
	let dragging = false;
	let fileInput: HTMLInputElement | null = null;
	let chat: ChatSurface;

	const formatSize = (size: number) => {
		if (!size) return '—';
		if (size < 1024) return `${size} B`;
		if (size < 1024 * 1024) return `${(size / 1024).toFixed(0)} KB`;
		return `${(size / (1024 * 1024)).toFixed(1)} MB`;
	};

	const updateDoc = (key: string, patch: Partial<UploadedDoc>) => {
		docs = docs.map((doc) => (doc.key === key ? { ...doc, ...patch } : doc));
	};

	const waitForText = async (key: string, id: string) => {
		const token = localStorage.token ?? '';
		for (let attempt = 0; attempt < 60; attempt += 1) {
			try {
				const text = await getFileIndexedText(token, id);
				if (text && text.trim()) {
					updateDoc(key, { status: 'ready', text });
					return;
				}
				const current = docs.find((doc) => doc.key === key);
				if (current?.status === 'uploading') updateDoc(key, { status: 'processing' });

				// Stop early when the pipeline already finished without any text.
				const record = await getFileById(token, id).catch(() => null);
				const state = record?.data?.status;
				if (state === 'failed') {
					updateDoc(key, {
						status: 'error',
						error: record?.data?.error || t('Processing failed')
					});
					return;
				}
				if (state === 'completed') {
					updateDoc(key, {
						status: 'error',
						error: t('No text could be extracted from this file.')
					});
					return;
				}
			} catch {
				// The file may still be processing; keep polling.
			}
			await new Promise((resolve) => setTimeout(resolve, 1500));
		}
		updateDoc(key, { status: 'ready', text: '' });
	};

	const handleFiles = async (fileList: FileList | null) => {
		if (!fileList?.length) return;

		for (const file of Array.from(fileList)) {
			const key = uuidv4();
			docs = [
				...docs,
				{ key, id: null, name: file.name, size: file.size, status: 'uploading', text: '' }
			];

			try {
				const uploaded = await uploadFile(localStorage.token ?? '', file, null, true, false);
				if (!uploaded?.id) throw new Error('Upload failed');
				updateDoc(key, { id: uploaded.id, status: 'processing' });
				void waitForText(key, uploaded.id);
			} catch (error) {
				updateDoc(key, {
					status: 'error',
					error: error instanceof Error ? error.message : String(error)
				});
			}
		}

		if (fileInput) fileInput.value = '';
	};

	const onDrop = (event: DragEvent) => {
		event.preventDefault();
		dragging = false;
		void handleFiles(event.dataTransfer?.files ?? null);
	};

	const onDragOver = (event: DragEvent) => {
		event.preventDefault();
		dragging = true;
	};

	const removeDoc = async (doc: UploadedDoc) => {
		docs = docs.filter((item) => item.key !== doc.key);
		if (doc.id) {
			try {
				await deleteFileById(localStorage.token ?? '', doc.id);
			} catch {
				// Non fatal: the file simply stays in the workspace.
			}
		}
	};

	const clearAll = async () => {
		const snapshot = [...docs];
		docs = [];
		chat?.reset();
		for (const doc of snapshot) {
			if (doc.id) {
				try {
					await deleteFileById(localStorage.token ?? '', doc.id);
				} catch {
					// ignore
				}
			}
		}
	};

	const systemPrompt =
		() => `You are a meticulous document analyst working entirely offline. The user has uploaded one or more documents; relevant excerpts are attached to each question as context blocks, each labelled with the file name and chunk number.

Rules:
- Answer only from the provided excerpts when the question is about the documents. If the answer is not present, say so explicitly and suggest what to look for.
- Cite the source of every factual statement using the file name and chunk number, e.g. [report.pdf #3].
- Quote short passages when precision matters; do not invent numbers, names or dates.
- For summaries, structure the answer with short sections. For comparisons across documents, use a compact table.
- If the question is unrelated to the documents, answer normally but make clear that the answer does not come from the uploaded files.
- Always reply in the language of the user's question.`;

	const prepareContext = async (question: string) => {
		const files = docs
			.filter((doc) => doc.status === 'ready' && doc.text.trim())
			.map((doc) => ({ id: doc.id ?? doc.key, name: doc.name, text: doc.text }));
		return buildFileContext(files, question);
	};
</script>

<div class="grid h-full min-h-0 grid-cols-1 gap-3 lg:grid-cols-12">
	<!-- Documents -->
	<section
		class="flex min-h-0 flex-col rounded-2xl border border-gray-100 bg-white lg:col-span-5 dark:border-gray-850 dark:bg-gray-900"
	>
		<header
			class="flex items-center justify-between gap-2 border-b border-gray-100 px-3 py-2 dark:border-gray-850"
		>
			<div class="flex items-center gap-1.5 text-xs font-semibold text-gray-700 dark:text-gray-200">
				<DocumentIcon className="size-3.5 text-gray-400" strokeWidth="1.8" />
				{t('Upload documents')}
				<span class="font-normal text-gray-400">({docs.length})</span>
			</div>
			{#if docs.length}
				<button
					class="rounded-md px-1.5 py-0.5 text-[10px] font-medium text-gray-500 transition hover:bg-gray-100 hover:text-gray-800 dark:text-gray-400 dark:hover:bg-gray-850"
					on:click={clearAll}
				>
					{t('Clear all')}
				</button>
			{/if}
		</header>

		<div class="scrollbar-hidden min-h-0 flex-1 overflow-y-auto p-2.5">
			{#if !canUpload}
				<div
					class="rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700 dark:bg-amber-500/10 dark:text-amber-300"
				>
					{t('File uploads are disabled for your account.')}
				</div>
			{:else}
				<button
					class="flex w-full flex-col items-center justify-center gap-1.5 rounded-xl border border-dashed px-3 py-5 text-center transition {dragging
						? 'border-sky-400 bg-sky-50/70 dark:border-sky-500 dark:bg-sky-500/10'
						: 'border-gray-200 bg-gray-50/50 hover:border-gray-300 hover:bg-gray-50 dark:border-gray-800 dark:bg-gray-900/40 dark:hover:border-gray-700'}"
					on:click={() => fileInput?.click()}
					on:dragover={onDragOver}
					on:dragleave={() => (dragging = false)}
					on:drop={onDrop}
				>
					<CloudArrowUpIcon className="size-6 text-gray-400" strokeWidth="1.5" />
					<span class="text-xs font-medium text-gray-600 dark:text-gray-300">
						{t('Drop files here or click to browse')}
					</span>
					<span class="max-w-sm text-[10px] leading-4 text-gray-400">
						{t('PDF, text, markdown, CSV, JSON, DOCX, XLSX. Files are parsed locally.')}
					</span>
				</button>
				<input
					bind:this={fileInput}
					type="file"
					multiple
					class="hidden"
					on:change={(event) => handleFiles((event.currentTarget as HTMLInputElement).files)}
				/>
			{/if}

			{#if !docs.length}
				<div class="mt-6 flex flex-col items-center gap-2 text-center">
					<div class="text-xs font-medium text-gray-500 dark:text-gray-400">
						{t('No documents yet')}
					</div>
					<p class="max-w-xs text-[11px] leading-5 text-gray-400">
						{t('Add a file to start asking questions about its content.')}
					</p>
				</div>
			{:else}
				<ul class="mt-2 flex flex-col gap-1.5">
					{#each docs as doc (doc.key)}
						<li
							class="group flex items-start gap-2 rounded-xl border border-gray-100 bg-gray-50/50 px-2.5 py-2 dark:border-gray-850 dark:bg-gray-850/40"
						>
							<div class="mt-0.5 text-gray-400">
								{#if doc.status === 'ready'}
									<CheckCircleIcon className="size-4 text-emerald-500" strokeWidth="1.8" />
								{:else if doc.status === 'error'}
									<InfoIcon className="size-4 text-red-500" strokeWidth="1.8" />
								{:else}
									<Spinner className="size-4" />
								{/if}
							</div>
							<div class="min-w-0 flex-1">
								<div class="truncate text-xs font-medium text-gray-700 dark:text-gray-200">
									{doc.name}
								</div>
								<div class="text-[10px] text-gray-400">
									{formatSize(doc.size)}
									{#if doc.status === 'uploading'}
										· {t('Uploading…')}
									{:else if doc.status === 'processing'}
										· {t('Processing…')}
									{:else if doc.status === 'ready' && doc.text}
										· {formatNumber(doc.text.length, locale)} {t('characters')}
									{:else if doc.status === 'ready'}
										· {t('No text could be extracted from this file.')}
									{:else if doc.error}
										· {doc.error}
									{/if}
								</div>
							</div>
							<button
								class="mt-0.5 rounded-md p-0.5 text-gray-400 opacity-60 transition hover:bg-gray-200/60 hover:text-gray-700 group-hover:opacity-100 dark:hover:bg-gray-800 dark:hover:text-gray-200"
								on:click={() => removeDoc(doc)}
								aria-label={t('Remove')}
							>
								<XMarkIcon className="size-3.5" strokeWidth="2" />
							</button>
						</li>
					{/each}
				</ul>
			{/if}

			<div
				class="mt-3 flex items-start gap-1.5 rounded-lg bg-gray-50 px-2 py-1.5 text-[10px] leading-4 text-gray-400 dark:bg-gray-850/40"
			>
				<InfoIcon className="mt-0.5 size-3 shrink-0" strokeWidth="1.8" />
				<span>
					{t(
						'Ask questions about one or more files. The most relevant passages are retrieved locally and sent to your model.'
					)}
				</span>
			</div>
		</div>
	</section>

	<!-- Chat -->
	<section
		class="flex min-h-[460px] flex-col overflow-hidden rounded-2xl border border-gray-100 bg-white lg:col-span-7 lg:min-h-0 dark:border-gray-850 dark:bg-gray-900"
	>
		<ChatSurface
			bind:this={chat}
			bind:modelId
			accent="emerald"
			systemPrompt={systemPrompt()}
			emptyTitle={t('File Analyst')}
			emptyDescription={isPersian
				? 'یک یا چند فایل اضافه کن و درباره محتوایشان بپرس. فقط مرتبط‌ترین بخش‌ها به مدل ارسال می‌شود.'
				: 'Add one or more files and ask about their content. Only the most relevant passages are sent to the model.'}
			placeholder={t('Ask about your documents…')}
			suggestions={isPersian
				? [
						'این سند را در پنج نکته خلاصه کن.',
						'اعداد و تاریخ‌های کلیدی را فهرست کن.',
						'ریسک‌ها و ابهام‌های اصلی سند چیست؟',
						'یک جمع‌بندی اجرایی یک‌صفحه‌ای بنویس.'
					]
				: [
						'Summarise this document in five bullet points.',
						'List the key numbers and dates.',
						'What are the main risks or open questions?',
						'Write a one-page executive summary.'
					]}
			{prepareContext}
		/>
	</section>
</div>
