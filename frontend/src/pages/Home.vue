<template>
	<div class="mx-auto max-w-3xl px-6 py-10">
		<h1 class="text-2xl font-semibold text-ink-gray-9">Welcome, {{ session.fullName }} 👋</h1>
		<p class="mt-2 text-base text-ink-gray-6">One Space. Everyone Connected.</p>

		<TodayAttendance class="mt-8" />

		<div class="mt-8 grid gap-3 sm:grid-cols-3">
			<router-link
				v-for="card in cards"
				:key="card.route"
				:to="card.route"
				class="rounded-lg border p-4 hover:bg-surface-gray-1"
			>
				<component :is="card.icon" class="size-5 text-ink-gray-6" />
				<div class="mt-2 text-base font-medium text-ink-gray-9">{{ card.title }}</div>
				<div class="mt-1 text-sm text-ink-gray-6">{{ card.description }}</div>
			</router-link>
		</div>

		<div v-if="myTasks.data" class="mt-10 flex items-center justify-between">
			<h2 class="text-base font-semibold text-ink-gray-9">My open tasks</h2>
			<router-link to="/tasks" class="text-sm text-ink-blue-3 hover:underline"
				>View all</router-link
			>
		</div>
		<div v-if="myTasks.data" class="mt-3">
			<div
				v-if="!myTasks.data.length"
				class="rounded-lg border px-4 py-6 text-center text-base text-ink-gray-5"
			>
				Nothing assigned to you 🎉
			</div>
			<div v-else class="grid gap-2 sm:grid-cols-2">
				<TaskCard
					v-for="task in myTasks.data.slice(0, 4)"
					:key="task.name"
					:task="task"
					show-status
					@open="chat.openTask(task.name)"
				/>
			</div>
		</div>

		<h2 class="mt-10 text-base font-semibold text-ink-gray-9">Recent conversations</h2>
		<div class="mt-3 divide-y rounded-lg border">
			<router-link
				v-for="channel in recent"
				:key="channel.name"
				:to="{ name: 'Conversation', params: { channel: channel.name } }"
				class="flex items-center gap-3 px-4 py-3 hover:bg-surface-gray-1"
			>
				<div class="min-w-0 flex-1">
					<div
						class="truncate text-base text-ink-gray-9"
						:class="{ 'font-semibold': channel.unread }"
					>
						{{
							["Public", "Private", "Announcement"].includes(channel.channel_type)
								? "#"
								: ""
						}}{{ chat.channelTitle(channel) }}
					</div>
					<div class="truncate text-sm text-ink-gray-5">
						{{ channel.last_message_preview }}
					</div>
				</div>
				<span
					v-if="channel.unread"
					class="rounded-full bg-surface-gray-7 px-1.5 text-xs leading-5 text-ink-white"
				>
					{{ channel.unread }}
				</span>
			</router-link>
			<div
				v-if="chat.sidebarLoaded && !recent.length"
				class="px-4 py-8 text-center text-base text-ink-gray-5"
			>
				No conversations yet. Find someone in People or browse Channels to get started.
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { createResource } from "frappe-ui";
import TaskCard from "@/components/TaskCard.vue";
import TodayAttendance from "@/components/TodayAttendance.vue";
import { useChat } from "@/stores/chat";
import { session } from "@/session";
import LucideUsers from "~icons/lucide/users";
import LucideHash from "~icons/lucide/hash";
import LucideFolderKanban from "~icons/lucide/folder-kanban";

const chat = useChat();
const myTasks = createResource({
	url: "aeraspace.api.task.get_tasks",
	params: { assignee: "me", include_done: 0 },
	auto: true,
	transform: (tasks) =>
		[...tasks].sort((a, b) => (a.due_date || "9999").localeCompare(b.due_date || "9999")),
});
const recent = computed(() => chat.sidebar.filter((c) => c.last_message_at).slice(0, 8));

const cards = [
	{
		title: "People",
		description: "Find teammates and start a chat",
		route: "/people",
		icon: LucideUsers,
	},
	{
		title: "Channels",
		description: "Team and project discussions",
		route: "/channels",
		icon: LucideHash,
	},
	{
		title: "Projects",
		description: "Boards, tasks and project channels",
		route: "/projects",
		icon: LucideFolderKanban,
	},
];
</script>
