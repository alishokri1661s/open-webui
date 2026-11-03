<script lang="ts">
	import { showSidebar } from '$lib/stores';
	import IntelWorkspace from '$lib/components/intel/IntelWorkspace.svelte';
</script>

<svelte:head>
	<title>Intelligence</title>
</svelte:head>

<div
	class="flex h-screen max-h-[100dvh] w-full max-w-full flex-col transition-width duration-200 ease-in-out {$showSidebar
		? 'md:max-w-[calc(100%-var(--sidebar-width))]'
		: ''}"
>
	<IntelWorkspace />
</div>
