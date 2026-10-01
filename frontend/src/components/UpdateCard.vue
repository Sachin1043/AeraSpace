<template>
	<div :class="flat ? '' : 'cursor-pointer rounded-lg border p-3 hover:bg-surface-gray-1'">
		<div v-if="!flat" class="mb-1 text-sm font-semibold text-ink-gray-8">
			{{ dayjs(update.update_date).format("dddd, D MMM YYYY") }}
		</div>
		<div class="grid gap-2 sm:grid-cols-2">
			<div v-for="s in shown" :key="s.field">
				<div class="text-xs font-medium text-ink-gray-5">{{ s.label }}</div>
				<!-- v-text keeps formatter line breaks out of the pre-wrapped text -->
				<div
					class="whitespace-pre-wrap text-sm text-ink-gray-8"
					v-text="update[s.field]"
				/>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { dayjs } from "frappe-ui";

const props = defineProps({
	update: { type: Object, required: true },
	flat: Boolean,
});

const sections = [
	{ field: "completed", label: "✅ Completed" },
	{ field: "in_progress", label: "🔄 In progress" },
	{ field: "blockers", label: "⛔ Blockers" },
	{ field: "tomorrow", label: "📅 Tomorrow" },
];
const shown = computed(() => sections.filter((s) => props.update[s.field]));
</script>
