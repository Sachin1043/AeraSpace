<template>
	<div class="mx-auto max-w-3xl px-6 py-8">
		<div class="flex items-center justify-between gap-4">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">Activity</h1>
				<p class="text-base text-ink-gray-6">
					Mentions, thread replies, invites and task updates.
				</p>
			</div>
			<Button v-if="chat.unreadNotifications" @click="markAll">Mark all as read</Button>
		</div>

		<div
			v-if="chat.notificationPermission === 'default'"
			class="mt-4 flex items-center justify-between gap-3 rounded-lg border border-outline-blue-1 bg-surface-blue-1 px-4 py-3"
		>
			<span class="text-base text-ink-blue-3"
				>🔔 Get desktop notifications when AeraSpace is in the background.</span
			>
			<Button variant="solid" @click="chat.enableDesktopNotifications()">Enable</Button>
		</div>
		<div
			v-else-if="chat.notificationPermission === 'denied'"
			class="mt-4 rounded-lg border px-4 py-3 text-sm text-ink-gray-6"
		>
			Desktop notifications are blocked in your browser settings for this site.
		</div>

		<div class="mt-4 flex gap-1">
			<button
				v-for="tab in tabs"
				:key="tab"
				class="rounded px-3 py-1 text-sm"
				:class="
					filter === tab
						? 'bg-surface-gray-3 font-medium text-ink-gray-9'
						: 'text-ink-gray-6 hover:bg-surface-gray-2'
				"
				@click="filter = tab"
			>
				{{ tab }}
			</button>
		</div>

		<div v-if="items.loading && !items.data" class="flex justify-center py-10">
			<LoadingIndicator class="size-5" />
		</div>
		<div
			v-else-if="!visible.length"
			class="mt-4 rounded-lg border px-4 py-10 text-center text-base text-ink-gray-5"
		>
			You're all caught up 🎉
		</div>
		<div v-else class="mt-4 divide-y rounded-lg border">
			<button
				v-for="n in visible"
				:key="n.name"
				class="flex w-full items-start gap-3 px-4 py-3 text-left hover:bg-surface-gray-1"
				:class="{ 'bg-surface-blue-1': !n.is_read }"
				@click="open(n)"
			>
				<UserAvatar :user="n.from_user" size="lg" :show-presence="false" />
				<div class="min-w-0 flex-1">
					<div class="flex items-center gap-2">
						<span
							class="rounded bg-surface-gray-2 px-1.5 text-2xs font-medium uppercase text-ink-gray-6"
							>{{ icons[n.notification_type] }} {{ n.notification_type }}</span
						>
						<span class="text-xs text-ink-gray-5">{{
							dayjsLocal(n.creation).fromNow()
						}}</span>
					</div>
					<div
						class="mt-1 text-base"
						:class="n.is_read ? 'text-ink-gray-7' : 'font-medium text-ink-gray-9'"
					>
						{{ title(n) }}
					</div>
					<div
						v-if="
							['Mention', 'Thread Reply'].includes(n.notification_type) && n.preview
						"
						class="line-clamp-2 text-sm text-ink-gray-6"
					>
						{{ plainText(n.preview, chat.person) }}
					</div>
				</div>
				<span v-if="!n.is_read" class="mt-2 size-2 shrink-0 rounded-full bg-blue-500" />
			</button>
		</div>
	</div>
</template>

<script setup>
import { computed, ref, watch } from "vue";
import { useRouter } from "vue-router";
import { Button, LoadingIndicator, createResource, dayjsLocal } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { plainText } from "@/utils/format";
import UserAvatar from "@/components/UserAvatar.vue";

const chat = useChat();
const router = useRouter();
const tabs = ["All", "Unread", "Mentions", "Threads", "Tasks"];
const filter = ref("All");
const icons = {
	Mention: "@",
	"Thread Reply": "💬",
	Invite: "➕",
	Assignment: "📋",
	"Task Update": "🔄",
	Reminder: "⏰",
	"Password Reset": "🔑",
};

const items = createResource({ url: "aeraspace.api.notifications.get_notifications", auto: true });
// refresh whenever a new notification arrives
watch(
	() => chat.unreadNotifications,
	(count, old) => count > old && items.reload()
);

const visible = computed(() =>
	(items.data || []).filter((n) => {
		if (filter.value === "Unread") return !n.is_read;
		if (filter.value === "Mentions") return n.notification_type === "Mention";
		if (filter.value === "Threads") return n.notification_type === "Thread Reply";
		if (filter.value === "Tasks") return !!n.task;
		return true;
	})
);

function title(n) {
	if (["Reminder", "Password Reset"].includes(n.notification_type)) return n.preview;
	const from = chat.person(n.from_user).full_name;
	const where =
		n.channel_type === "Direct"
			? ""
			: n.channel_name
			? ` in #${n.channel_name}`
			: n.channel_type === "Group"
			? " in a group"
			: "";
	if (n.notification_type === "Mention") return `${from} mentioned you${where}`;
	if (n.notification_type === "Thread Reply")
		return `${from} replied to a thread you follow${where}`;
	if (["Assignment", "Task Update"].includes(n.notification_type))
		return `${from} ${plainText(n.preview, chat.person)}`;
	if (n.task) return `${from} mentioned you on ${n.task}`;
	return `${from} ${n.preview}${n.channel_name ? ` #${n.channel_name}` : ""}`;
}

async function open(n) {
	if (!n.is_read) {
		n.is_read = 1;
		chat.markNotificationsRead([n.name]);
	}
	router.push(chat.notificationRoute(n));
}

async function markAll() {
	await chat.markNotificationsRead();
	items.reload();
}
</script>
