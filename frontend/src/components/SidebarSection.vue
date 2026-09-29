<template>
	<div class="mt-5">
		<div class="group flex items-center justify-between px-2 pb-1">
			<span class="text-xs font-medium uppercase tracking-wide text-ink-gray-5">{{
				title
			}}</span>
			<button
				class="rounded p-0.5 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-8"
				:title="addLabel"
				@click="$emit('add')"
			>
				<LucidePlus class="size-3.5" />
			</button>
		</div>
		<div class="space-y-0.5">
			<slot />
		</div>
	</div>
</template>

<script setup>
import LucidePlus from "~icons/lucide/plus";

defineProps({ title: String, addLabel: String });
defineEmits(["add"]);
</script>
