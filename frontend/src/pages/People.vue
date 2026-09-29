<template>
	<div class="mx-auto max-w-5xl px-6 py-8">
		<div class="flex items-center justify-between gap-4">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">People</h1>
				<p class="text-base text-ink-gray-6">
					{{ chat.peopleList.length }} people at Aerele
				</p>
			</div>
			<TextInput
				v-model="search"
				class="w-72"
				placeholder="Search by name, role, team, skill"
			>
				<template #prefix><LucideSearch class="size-4 text-ink-gray-5" /></template>
			</TextInput>
		</div>

		<div class="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
			<button
				v-for="p in results"
				:key="p.user"
				class="flex items-start gap-3 rounded-lg border p-4 text-left hover:bg-surface-gray-1"
				@click="openProfile(p.user)"
			>
				<UserAvatar :user="p.user" size="xl" />
				<div class="min-w-0">
					<div class="truncate text-base font-medium text-ink-gray-9">
						{{ chat.listName(p.user) }}
					</div>
					<div class="truncate text-sm text-ink-gray-6">{{ p.designation || "—" }}</div>
					<div class="truncate text-sm text-ink-gray-5">
						{{ [p.department, p.team].filter(Boolean).join(" · ") }}
					</div>
					<div
						v-if="p.status_text || p.status_emoji"
						class="mt-1 truncate text-sm text-ink-gray-6"
					>
						{{ p.status_emoji }} {{ p.status_text }}
					</div>
				</div>
			</button>
		</div>
		<div v-if="!results.length" class="py-16 text-center text-base text-ink-gray-5">
			No one matches "{{ search }}"
		</div>
	</div>
</template>

<script setup>
import { computed, ref } from "vue";
import { TextInput } from "frappe-ui";
import { useChat } from "@/stores/chat";
import UserAvatar from "@/components/UserAvatar.vue";
import LucideSearch from "~icons/lucide/search";

const chat = useChat();
const search = ref("");

const results = computed(() => {
	const term = search.value.trim().toLowerCase();
	if (!term) return chat.peopleList;
	return chat.peopleList.filter((p) =>
		[p.full_name, p.user, p.designation, p.department, p.team, p.skills].some((v) =>
			v?.toLowerCase().includes(term)
		)
	);
});

function openProfile(user) {
	chat.viewProfile(user);
}
</script>
