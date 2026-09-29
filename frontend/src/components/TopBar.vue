<template>
	<header class="flex h-12 shrink-0 items-center gap-3 border-b bg-surface-gray-1 pl-4 pr-3">
		<router-link to="/" class="flex w-52 shrink-0 items-center gap-2">
			<div
				class="flex size-7 items-center justify-center rounded-md bg-surface-gray-7 text-sm font-semibold text-ink-white"
			>
				A
			</div>
			<span class="text-base font-semibold text-ink-gray-9">AeraSpace</span>
		</router-link>

		<div
			class="flex h-8 w-full max-w-xl items-center gap-2 rounded-md border bg-surface-white px-2.5 focus-within:border-outline-gray-4"
		>
			<LucideSearch class="size-4 shrink-0 text-ink-gray-5" />
			<input
				ref="box"
				v-model="query"
				class="h-full w-full border-0 bg-transparent p-0 text-base text-ink-gray-9 placeholder-ink-gray-4 focus:ring-0"
				placeholder="Search messages, files, tasks, people…"
				@keydown.enter="search"
				@keydown.esc="
					query = '';
					box.blur();
				"
			/>
			<kbd class="hidden shrink-0 rounded border px-1 text-2xs text-ink-gray-5 sm:block"
				>Ctrl K</kbd
			>
		</div>

		<div class="ml-auto flex items-center gap-1">
			<router-link
				to="/activity"
				class="relative rounded-md p-1.5 text-ink-gray-6 hover:bg-surface-gray-3"
				title="Activity"
			>
				<LucideBell class="size-5" />
				<span
					v-if="chat.unreadNotifications"
					class="absolute -right-0.5 -top-0.5 min-w-[1.1rem] rounded-full bg-red-500 px-1 text-center text-2xs font-medium leading-4 text-white"
				>
					{{ chat.unreadNotifications > 99 ? "99+" : chat.unreadNotifications }}
				</span>
			</router-link>
			<StatusMenu />
		</div>
	</header>
</template>

<script setup>
import { ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useChat } from "@/stores/chat";
import StatusMenu from "./StatusMenu.vue";
import LucideSearch from "~icons/lucide/search";
import LucideBell from "~icons/lucide/bell";

const chat = useChat();
const route = useRoute();
const router = useRouter();
const box = ref(null);
const query = ref("");

function search() {
	const q = query.value.trim();
	if (q) router.push({ name: "Search", query: { q } });
}

// keep the box in step with the search page
watch(
	() => route.query.q,
	(q) => route.name === "Search" && (query.value = q || ""),
	{ immediate: true }
);

defineExpose({ focus: () => box.value?.focus() });
</script>
