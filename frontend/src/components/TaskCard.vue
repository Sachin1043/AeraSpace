<template>
	<div
		class="cursor-pointer rounded-lg border bg-surface-white p-2.5 shadow-sm hover:border-outline-gray-3"
		:class="{ 'opacity-40': dragging }"
		@click="$emit('open', task)"
	>
		<div class="flex items-center gap-2 text-xs text-ink-gray-5">
			<span class="font-medium">{{ task.name }}</span>
			<span
				class="rounded px-1.5 py-px text-2xs font-medium"
				:class="PRIORITY_STYLES[task.priority]"
				>{{ task.priority }}</span
			>
			<span v-if="showStatus" class="ml-auto flex items-center gap-1">
				<span class="size-2 rounded-full" :class="STATUS_COLORS[task.status]" />{{
					task.status
				}}
			</span>
		</div>
		<div
			class="mt-1 text-base leading-snug text-ink-gray-9"
			:class="{ 'line-through opacity-60': task.status === 'Done' }"
		>
			{{ task.title }}
		</div>
		<div v-if="task.labels?.length" class="mt-1.5 flex flex-wrap gap-1">
			<span
				v-for="label in task.labels"
				:key="label"
				class="rounded bg-surface-gray-2 px-1.5 text-2xs text-ink-gray-7"
				>{{ label }}</span
			>
		</div>
		<div class="mt-2 flex items-center gap-2 text-xs text-ink-gray-5">
			<span
				v-if="due"
				class="flex items-center gap-1"
				:class="
					due.overdue ? 'font-medium text-ink-red-4' : due.soon ? 'text-ink-amber-3' : ''
				"
			>
				<LucideCalendar class="size-3" />{{ due.text }}
			</span>
			<span v-if="task.comment_count" class="flex items-center gap-1"
				><LucideMessageSquare class="size-3" />{{ task.comment_count }}</span
			>
			<span v-if="task.files?.length" class="flex items-center gap-1"
				><LucidePaperclip class="size-3" />{{ task.files.length }}</span
			>
			<span class="ml-auto">
				<UserAvatar
					v-if="task.assignee"
					:user="task.assignee"
					size="xs"
					:show-presence="false"
				/>
				<span v-else class="text-2xs italic">Unassigned</span>
			</span>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { PRIORITY_STYLES, STATUS_COLORS, dueLabel } from "@/utils/tasks";
import UserAvatar from "./UserAvatar.vue";
import LucideCalendar from "~icons/lucide/calendar";
import LucideMessageSquare from "~icons/lucide/message-square";
import LucidePaperclip from "~icons/lucide/paperclip";

const props = defineProps({
	task: { type: Object, required: true },
	dragging: Boolean,
	showStatus: Boolean,
});
defineEmits(["open"]);
const due = computed(() => dueLabel(props.task));
</script>
