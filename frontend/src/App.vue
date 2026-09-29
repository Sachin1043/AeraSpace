<template>
	<FrappeUIProvider>
		<div class="flex h-full w-full flex-col overflow-hidden bg-surface-white">
			<TopBar ref="topBar" />
			<div class="relative flex min-h-0 flex-1">
				<AppSidebar v-if="!sidebarCollapsed" />
				<main class="min-w-0 flex-1 overflow-auto">
					<router-view />
				</main>

				<!-- hidden sidebar: a small tab on the left edge brings it back -->
				<Tooltip v-if="sidebarCollapsed" text="Show sidebar" placement="right">
					<button
						class="absolute bottom-16 left-0 z-30 flex h-10 w-4 items-center justify-center rounded-r-md border border-l-0 bg-surface-gray-2 text-ink-gray-6 shadow-sm hover:w-5 hover:bg-surface-gray-3 hover:text-ink-gray-9"
						aria-label="Show sidebar"
						@click="showSidebar"
					>
						<LucideChevronRight class="size-3.5" />
					</button>
				</Tooltip>
			</div>
		</div>
		<ProfileDrawer />
	</FrappeUIProvider>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref } from "vue";
import { FrappeUIProvider, Tooltip } from "frappe-ui";
import AppSidebar from "@/components/AppSidebar.vue";
import TopBar from "@/components/TopBar.vue";
import ProfileDrawer from "@/components/ProfileDrawer.vue";
import { showError, useChat } from "@/stores/chat";
import { sidebarCollapsed } from "@/layout";
import LucideChevronRight from "~icons/lucide/chevron-right";

const chat = useChat();
const topBar = ref(null);
onMounted(() => chat.init().catch(showError));

function showSidebar() {
	sidebarCollapsed.value = false;
}

// Ctrl/Cmd + K focuses the search box in the top bar
function onKeydown(event) {
	if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
		event.preventDefault();
		topBar.value?.focus();
	}
}
onMounted(() => window.addEventListener("keydown", onKeydown));
onBeforeUnmount(() => window.removeEventListener("keydown", onKeydown));
</script>
