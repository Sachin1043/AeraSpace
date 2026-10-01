<template>
	<aside class="flex h-full w-60 shrink-0 flex-col border-r bg-surface-gray-1">
		<div class="flex-1 overflow-y-auto px-2 pb-4 pt-2">
			<nav class="space-y-0.5">
				<router-link
					v-for="item in navItems"
					:key="item.route"
					:to="item.route"
					class="flex items-center gap-2 rounded px-2 py-1.5 text-base text-ink-gray-7 hover:bg-surface-gray-3"
					:class="{ 'bg-surface-white text-ink-gray-9 shadow-sm': isActive(item.route) }"
				>
					<component :is="item.icon" class="size-4" />
					<span class="flex-1">{{ item.label }}</span>
					<span
						v-if="item.badge?.()"
						class="rounded-full bg-red-500 px-1.5 text-xs font-medium leading-5 text-ink-white"
					>
						{{ item.badge() > 99 ? "99+" : item.badge() }}
					</span>
					<span v-if="item.shortcut" class="text-2xs text-ink-gray-4">{{
						item.shortcut
					}}</span>
				</router-link>
			</nav>

			<SidebarSection
				title="Channels"
				add-label="Create channel"
				@add="showCreateChannel = true"
			>
				<SidebarItem
					v-for="channel in chat.channels"
					:key="channel.name"
					:channel="channel"
					:active="activeChannel === channel.name"
				>
					<template #icon>
						<LucideFolderKanban v-if="channel.project" class="size-3.5" />
						<LucideLock
							v-else-if="channel.channel_type === 'Private'"
							class="size-3.5"
						/>
						<LucideMegaphone
							v-else-if="channel.channel_type === 'Announcement'"
							class="size-3.5"
						/>
						<LucideHash v-else class="size-3.5" />
					</template>
				</SidebarItem>
				<router-link
					to="/channels"
					class="flex items-center gap-2 rounded px-2 py-1 text-sm text-ink-gray-5 hover:bg-surface-gray-3"
				>
					<LucidePlus class="size-3.5" /> Browse channels
				</router-link>
			</SidebarSection>

			<SidebarSection
				title="Direct messages"
				add-label="New message"
				@add="showNewMessage = true"
			>
				<SidebarItem
					v-for="channel in chat.directMessages"
					:key="channel.name"
					:channel="channel"
					:active="activeChannel === channel.name"
				>
					<template #icon>
						<PresenceDot
							v-if="channel.channel_type === 'Direct'"
							:status="chat.statusOf(chat.dmPartner(channel))"
							size="md"
						/>
						<LucideUsers v-else class="size-3.5" />
					</template>
				</SidebarItem>
				<div
					v-if="chat.sidebarLoaded && !chat.directMessages.length"
					class="px-2 py-1 text-sm text-ink-gray-5"
				>
					No conversations yet
				</div>
			</SidebarSection>
		</div>

		<div class="flex items-center border-t px-2 py-1.5">
			<Tooltip text="Hide sidebar" placement="right">
				<button
					class="rounded p-1.5 text-ink-gray-5 hover:bg-surface-gray-3 hover:text-ink-gray-8"
					aria-label="Hide sidebar"
					@click="hide"
				>
					<LucidePanelLeftClose class="size-4" />
				</button>
			</Tooltip>
		</div>

		<CreateChannelDialog v-model="showCreateChannel" />
		<NewMessageDialog v-model="showNewMessage" />
	</aside>
</template>

<script setup>
import { computed, ref } from "vue";
import { useRoute } from "vue-router";
import { Tooltip } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { sidebarCollapsed } from "@/layout";
import SidebarSection from "./SidebarSection.vue";
import SidebarItem from "./SidebarItem.vue";
import PresenceDot from "./PresenceDot.vue";
import LucidePanelLeftClose from "~icons/lucide/panel-left-close";
import CreateChannelDialog from "./CreateChannelDialog.vue";
import NewMessageDialog from "./NewMessageDialog.vue";
import LucideHouse from "~icons/lucide/house";
import LucideUsers from "~icons/lucide/users";
import LucideHash from "~icons/lucide/hash";
import LucideLock from "~icons/lucide/lock";
import LucideMegaphone from "~icons/lucide/megaphone";
import LucideBookmark from "~icons/lucide/bookmark";
import LucidePlus from "~icons/lucide/plus";
import LucideFolderKanban from "~icons/lucide/folder-kanban";
import LucideListTodo from "~icons/lucide/list-todo";
import LucideClipboardCheck from "~icons/lucide/clipboard-check";
import LucideTimer from "~icons/lucide/timer";
import LucideBell from "~icons/lucide/bell";

const chat = useChat();
const route = useRoute();
const showCreateChannel = ref(false);
const showNewMessage = ref(false);

const activeChannel = computed(() => route.params.channel);

const navItems = [
	{ label: "Home", route: "/", icon: LucideHouse },
	{
		label: "Activity",
		route: "/activity",
		icon: LucideBell,
		badge: () => chat.unreadNotifications,
	},
	{ label: "People", route: "/people", icon: LucideUsers },
	{ label: "Saved", route: "/saved", icon: LucideBookmark },
	{ label: "Projects", route: "/projects", icon: LucideFolderKanban },
	{ label: "Tasks", route: "/tasks", icon: LucideListTodo },
	{ label: "EOD", route: "/eod", icon: LucideClipboardCheck },
	{ label: "Timesheets", route: "/timesheets", icon: LucideTimer },
];

function hide() {
	sidebarCollapsed.value = true;
}

function isActive(path) {
	return path === "/" ? route.path === "/" : route.path.startsWith(path);
}
</script>
