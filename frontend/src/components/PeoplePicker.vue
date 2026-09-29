<template>
	<div class="space-y-2">
		<div v-if="modelValue.length" class="flex flex-wrap gap-1">
			<button
				v-for="user in modelValue"
				:key="user"
				class="flex items-center gap-1 rounded bg-surface-gray-2 px-2 py-0.5 text-sm text-ink-gray-8 hover:bg-surface-gray-3"
				@click="toggle(user)"
			>
				{{ chat.listName(user) }}
				<LucideX class="size-3" />
			</button>
		</div>
		<TextInput v-model="search" placeholder="Search people" autofocus />
		<div class="max-h-60 overflow-y-auto rounded border">
			<label
				v-for="p in results"
				:key="p.user"
				class="flex cursor-pointer items-center gap-2 px-3 py-2 hover:bg-surface-gray-1"
			>
				<input
					type="checkbox"
					class="rounded"
					:checked="modelValue.includes(p.user)"
					@change="toggle(p.user)"
				/>
				<UserAvatar :user="p.user" size="sm" />
				<div class="min-w-0">
					<div class="truncate text-base text-ink-gray-9">{{ p.full_name }}</div>
					<div class="truncate text-sm text-ink-gray-5">
						{{ p.designation || p.user }}
					</div>
				</div>
			</label>
			<div v-if="!results.length" class="px-3 py-4 text-center text-sm text-ink-gray-5">
				No one found
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { TextInput } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { session } from "@/session";
import UserAvatar from "./UserAvatar.vue";
import LucideX from "~icons/lucide/x";

const props = defineProps({
	modelValue: { type: Array, default: () => [] },
	exclude: { type: Array, default: () => [] },
});
const emit = defineEmits(["update:modelValue"]);

const chat = useChat();
const search = ref("");

const results = computed(() => {
	const term = search.value.trim().toLowerCase();
	const hidden = new Set([session.user, ...props.exclude]);
	return chat.peopleList.filter(
		(p) =>
			!hidden.has(p.user) &&
			(!term ||
				[p.full_name, p.user, p.designation, p.department].some((v) =>
					v?.toLowerCase().includes(term)
				))
	);
});

function toggle(user) {
	const selected = props.modelValue.includes(user)
		? props.modelValue.filter((u) => u !== user)
		: [...props.modelValue, user];
	emit("update:modelValue", selected);
}
</script>
