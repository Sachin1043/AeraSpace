<template>
	<div class="flex min-h-full items-center justify-center px-4 py-12">
		<div class="w-full max-w-sm">
			<div class="mb-6 flex flex-col items-center gap-2 text-center">
				<div
					class="flex size-11 items-center justify-center rounded-xl bg-surface-gray-7 text-lg font-semibold text-ink-white"
				>
					A
				</div>
				<div class="text-xl font-semibold text-ink-gray-9">{{ title }}</div>
				<div v-if="subtitle" class="text-base text-ink-gray-6">{{ subtitle }}</div>
			</div>
			<div class="rounded-xl border bg-surface-white p-6 shadow-sm">
				<slot />
			</div>
			<div class="mt-4 text-center text-sm text-ink-gray-5"><slot name="footer" /></div>
		</div>
	</div>
</template>

<script setup>
defineProps({ title: String, subtitle: String });
</script>
