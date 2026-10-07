<template>
	<div class="flex h-full">
		<div
			class="relative flex min-w-0 flex-1 flex-col"
			@dragenter.prevent="onDragEnter"
			@dragover.prevent
			@dragleave="onDragLeave"
			@drop.prevent="onDrop"
		>
			<!-- header -->
			<header class="flex h-12 shrink-0 items-center gap-3 border-b px-4">
				<template v-if="details">
					<button
						v-if="partner"
						class="-ml-1 mr-auto flex min-w-0 items-center gap-3 rounded px-1.5 py-0.5 text-left outline-none hover:bg-surface-gray-2 focus-visible:ring-1 focus-visible:ring-outline-gray-3"
						title="View profile"
						@click="chat.viewProfile(partner)"
					>
						<UserAvatar :user="partner" size="lg" />
						<div class="min-w-0">
							<div class="truncate text-base font-semibold text-ink-gray-9">
								{{ title }}
							</div>
							<div class="truncate text-xs text-ink-gray-5">
								{{ chat.statusLabel(partner) }}
							</div>
						</div>
					</button>
					<template v-else>
						<component :is="headerIcon" class="size-4 text-ink-gray-6" />
						<div class="min-w-0 flex-1">
							<div class="truncate text-base font-semibold text-ink-gray-9">
								{{ title }}
							</div>
							<div v-if="subtitle" class="truncate text-xs text-ink-gray-5">
								{{ subtitle }}
							</div>
						</div>
					</template>
					<button
						v-if="details.project"
						class="header-btn"
						title="Project board"
						@click="
							router.push({ name: 'Project', params: { project: details.project } })
						"
					>
						<LucideKanban class="size-4" /> Board
					</button>
					<button class="header-btn" title="Pinned messages" @click="showPinned = true">
						<LucidePin class="size-4" />
						<span v-if="details.pinned_count">{{ details.pinned_count }}</span>
					</button>
					<button class="header-btn" title="Files" @click="showFiles = true">
						<LucideFolderOpen class="size-4" />
					</button>
					<button
						v-if="details.channel_type !== 'Direct'"
						class="header-btn"
						title="Members"
						@click="showMembers = true"
					>
						<LucideUsers class="size-4" /> {{ details.members.length }}
					</button>
					<Dropdown v-if="menu.length" :options="menu" placement="right">
						<Button variant="ghost"><LucideEllipsis class="size-4" /></Button>
					</Dropdown>
				</template>
			</header>

			<MessageList
				v-if="convo.loaded"
				ref="list"
				:key="channel"
				:channel="channel"
				:messages="convo.messages"
				:has-more="convo.hasMore"
				:loading="convo.loading"
				:intro="intro"
				:greeting="greeting"
				:readers="readers"
				:can-interact="!!details?.is_member"
				:can-post-top-level="canPost"
				:is-admin="isAdmin"
				:highlight="highlight"
				class="flex-1"
				@open-thread="openThread"
				@reply="(m) => (replyTo = m)"
				@create-task="startTask"
				@say-hello="(text) => chat.send(channel, text)"
			/>
			<div v-else class="flex flex-1 items-center justify-center">
				<LoadingIndicator class="size-5" />
			</div>

			<!-- composer / join bar / announcement notice -->
			<div class="shrink-0 px-4 pb-4">
				<div class="h-5 text-xs text-ink-gray-5">
					{{ typingNames(chat.typingUsers(channel)) }}
				</div>
				<Composer
					v-if="details?.is_member && canPost"
					ref="composer"
					:key="channel"
					:channel="channel"
					:reply-to="replyTo"
					:members="memberUsers"
					:placeholder="placeholder"
					@send="onSend"
					@typing="chat.notifyTyping(channel)"
					@cancel-reply="replyTo = null"
				/>
				<div
					v-else-if="details?.is_member"
					class="rounded-lg border bg-surface-gray-1 px-4 py-3 text-base text-ink-gray-6"
				>
					📣 Only admins can post in <b>#{{ details.channel_name }}</b
					>. You can react and reply in threads.
				</div>
				<div
					v-else-if="details"
					class="flex items-center justify-between rounded-lg border bg-surface-gray-1 px-4 py-3"
				>
					<span class="text-base text-ink-gray-7"
						>You're viewing <b>#{{ details.channel_name }}</b></span
					>
					<Button variant="solid" :loading="joining" @click="join">Join channel</Button>
				</div>
			</div>

			<!-- drop zone -->
			<div
				v-if="dragging && details?.is_member"
				class="pointer-events-none absolute inset-2 z-20 flex items-center justify-center rounded-xl border-2 border-dashed border-outline-blue-1 bg-surface-blue-1"
			>
				<div class="text-lg font-medium text-ink-blue-3">
					Drop files to share in {{ title }}
				</div>
			</div>
		</div>

		<ThreadPanel
			v-if="threadRoot && details"
			:root="threadRoot"
			:channel="channel"
			:channel-title="
				details.channel_type === 'Direct' || details.channel_type === 'Group'
					? title
					: `#${title}`
			"
			:can-interact="details.is_member"
			:is-admin="isAdmin"
			:typing-names="typingNames"
			:members="memberUsers"
			@close="closeThread"
			@create-task="startTask"
		/>

		<!-- members -->
		<Dialog
			v-if="details"
			v-model="showMembers"
			:options="{ title: `Members (${details.members.length})`, size: 'md' }"
		>
			<template #body-content>
				<div class="max-h-80 space-y-1 overflow-y-auto">
					<div
						v-for="m in details.members"
						:key="m.user"
						class="flex items-center gap-3 rounded px-2 py-1.5 hover:bg-surface-gray-1"
					>
						<button
							class="flex min-w-0 flex-1 items-center gap-3 text-left"
							@click="
								chat.viewProfile(m.user);
								showMembers = false;
							"
						>
							<UserAvatar :user="m.user" size="md" />
							<div class="min-w-0 flex-1">
								<div class="truncate text-base text-ink-gray-9">
									{{ chat.listName(m.user) }}
								</div>
								<div class="truncate text-sm text-ink-gray-5">
									{{ chat.person(m.user).designation }}
								</div>
							</div>
						</button>
						<Dropdown
							v-if="isAdmin && m.user !== session.user"
							:options="[
								m.role === 'Admin'
									? {
											label: 'Remove admin',
											onClick: () => setRole(m.user, 'Member'),
									  }
									: {
											label: 'Make admin',
											onClick: () => setRole(m.user, 'Admin'),
									  },
							]"
						>
							<button
								class="rounded px-1.5 py-0.5 text-xs text-ink-gray-5 hover:bg-surface-gray-3"
							>
								{{ m.role === "Admin" ? "Admin" : "Member" }} ▾
							</button>
						</Dropdown>
						<span v-else-if="m.role === 'Admin'" class="text-xs text-ink-gray-5"
							>Admin</span
						>
					</div>
				</div>
			</template>
			<template v-if="details.is_member" #actions>
				<Button
					class="w-full"
					@click="
						showMembers = false;
						showAdd = true;
					"
				>
					<template #prefix><LucideUserPlus class="size-4" /></template>
					Add people
				</Button>
			</template>
		</Dialog>
		<AddMembersDialog
			v-if="details"
			v-model="showAdd"
			:channel="channel"
			:existing="details.members.map((m) => m.user)"
			@added="loadDetails"
		/>
		<PinnedDialog v-model="showPinned" :channel="channel" @jump="jumpTo" />
		<FilesDialog v-model="showFiles" :channel="channel" />
		<CreateTaskDialog
			v-model="showCreateTask"
			:default-project="details?.project"
			:source-message="taskSource"
			@created="(t) => chat.openTask(t.name, t.project)"
		/>
	</div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Button, Dialog, Dropdown, LoadingIndicator, call } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { session } from "@/session";
import MessageList from "@/components/MessageList.vue";
import Composer from "@/components/Composer.vue";
import ThreadPanel from "@/components/ThreadPanel.vue";
import UserAvatar from "@/components/UserAvatar.vue";
import AddMembersDialog from "@/components/AddMembersDialog.vue";
import PinnedDialog from "@/components/PinnedDialog.vue";
import FilesDialog from "@/components/FilesDialog.vue";
import CreateTaskDialog from "@/components/CreateTaskDialog.vue";
import LucideKanban from "~icons/lucide/square-kanban";
import LucideHash from "~icons/lucide/hash";
import LucideLock from "~icons/lucide/lock";
import LucideMegaphone from "~icons/lucide/megaphone";
import LucideUsers from "~icons/lucide/users";
import LucideUserPlus from "~icons/lucide/user-plus";
import LucideEllipsis from "~icons/lucide/ellipsis";
import LucidePin from "~icons/lucide/pin";
import LucideFolderOpen from "~icons/lucide/folder-open";

const props = defineProps({ channel: { type: String, required: true } });
const chat = useChat();
const route = useRoute();
const router = useRouter();

const details = ref(null);
const joining = ref(false);
const showMembers = ref(false);
const showAdd = ref(false);
const showPinned = ref(false);
const showFiles = ref(false);
const replyTo = ref(null);
const showCreateTask = ref(false);
const taskSource = ref(null);

function startTask(message) {
	taskSource.value = message;
	showCreateTask.value = true;
}
const dragging = ref(false);
const list = ref(null);
const composer = ref(null);
let dragDepth = 0;

const convo = computed(() => chat.conversation(props.channel));
const threadRoot = computed(() => route.query.thread || null);
const highlight = computed(() => route.query.message || null);
const isAdmin = computed(() => details.value?.my_role === "Admin");
const canPost = computed(() => details.value?.channel_type !== "Announcement" || isAdmin.value);

const titleSource = computed(() => ({
	...details.value,
	members: (details.value?.members || []).map((m) => m.user),
}));
const title = computed(() => chat.channelTitle(titleSource.value));
const partner = computed(() => chat.dmPartner(titleSource.value));
const headerIcon = computed(() => {
	const type = details.value?.channel_type;
	if (type === "Private") return LucideLock;
	if (type === "Announcement") return LucideMegaphone;
	if (type === "Group") return LucideUsers;
	return LucideHash;
});
const placeholder = computed(() => {
	const type = details.value?.channel_type;
	return `Message ${type === "Direct" || type === "Group" ? title.value : "#" + title.value}`;
});

// channels show their description under the name; direct chats show availability instead
const subtitle = computed(() => details.value?.description || "");

const intro = computed(() => {
	const type = details.value?.channel_type;
	if (!type) return "";
	if (type === "Direct")
		return `This is the beginning of your conversation with ${title.value}.`;
	if (type === "Group") return "This is the beginning of the group conversation.";
	return `This is the very beginning of #${title.value}.`;
});

// what the "Say hello" button sends (only where you can post)
const greeting = computed(() => {
	if (!details.value?.is_member || !canPost.value) return "";
	if (details.value.channel_type === "Direct") {
		return partner.value && partner.value !== session.user
			? `Hello ${chat.person(partner.value).full_name} 👋`
			: "";
	}
	return "Hello everyone 👋";
});

function typingNames(users) {
	const names = users.map((u) => chat.person(u).full_name.split(" ")[0]);
	if (!names.length) return "";
	if (names.length === 1) return `${names[0]} is typing…`;
	if (names.length === 2) return `${names[0]} and ${names[1]} are typing…`;
	return "Several people are typing…";
}

const memberUsers = computed(() => (details.value?.members || []).map((m) => m.user));

const notifyLabels = {
	Default: "Default",
	All: "All new messages",
	Mentions: "Mentions & threads only",
	Nothing: "Nothing (mute)",
};

const menu = computed(() => {
	if (!details.value?.is_member) return [];
	const entry = chat.sidebarEntry(props.channel);
	const current = entry?.notify || "Default";
	const notifyGroup = {
		group: "Notify me about",
		items: Object.entries(notifyLabels).map(([level, label]) => ({
			label: `${current === level ? "✓ " : ""}${label}`,
			onClick: () => chat.setChannelNotify(props.channel, level),
		})),
	};
	if (details.value.channel_type === "Direct") return [notifyGroup];
	return [
		{
			group: "Channel",
			items: [
				{ label: "Add people", icon: "user-plus", onClick: () => (showAdd.value = true) },
				{ label: "Leave", icon: "log-out", onClick: leave },
			],
		},
		notifyGroup,
	];
});

async function loadDetails() {
	details.value = await call("aeraspace.api.chat.get_channel", { channel: props.channel });
	chat.setReadMarks(props.channel, details.value.members);
}

// everyone else in the conversation, with how far they've read (kept live by as_read events)
const readers = computed(() =>
	Object.entries(chat.readMarks[props.channel] || {})
		.filter(([user]) => user !== session.user)
		.map(([user, last_read_at]) => ({ user, last_read_at }))
);

async function open() {
	chat.activeChannel = props.channel;
	details.value = null;
	replyTo.value = null;
	try {
		await Promise.all([loadDetails(), chat.loadMessages(props.channel)]);
		chat.markRead(props.channel);
	} catch (error) {
		showError(error);
		router.replace("/");
	}
}

function onSend({ content, files }) {
	chat.send(props.channel, content, { files, replyTo: replyTo.value });
	replyTo.value = null;
}

function openThread(message) {
	router.replace({ query: { ...route.query, thread: message.name } });
}

function closeThread() {
	chat.activeThread = null;
	const { thread, ...query } = route.query;
	router.replace({ query });
}

async function jumpTo(message) {
	if (!convo.value.messages.some((m) => m.name === message.name))
		await chat.loadMessages(props.channel);
	router.replace({ query: { ...route.query, message: message.name } });
	await nextTick();
	list.value?.scrollToMessage(message.name);
}

async function join() {
	joining.value = true;
	try {
		await call("aeraspace.api.channel.join_channel", { channel: props.channel });
		await Promise.all([loadDetails(), chat.loadSidebar()]);
	} catch (error) {
		showError(error);
	} finally {
		joining.value = false;
	}
}

async function leave() {
	try {
		await call("aeraspace.api.channel.leave_channel", { channel: props.channel });
		await chat.loadSidebar();
		router.push("/");
	} catch (error) {
		showError(error);
	}
}

async function setRole(user, role) {
	try {
		await call("aeraspace.api.channel.set_member_role", {
			channel: props.channel,
			user,
			role,
		});
		await loadDetails();
	} catch (error) {
		showError(error);
	}
}

// ---- drag & drop ------------------------------------------------------

function hasFiles(event) {
	return [...(event.dataTransfer?.types || [])].includes("Files");
}

function onDragEnter(event) {
	if (!hasFiles(event)) return;
	dragDepth++;
	dragging.value = true;
}

function onDragLeave() {
	dragDepth = Math.max(0, dragDepth - 1);
	if (!dragDepth) dragging.value = false;
}

function onDrop(event) {
	dragDepth = 0;
	dragging.value = false;
	const files = [...(event.dataTransfer?.files || [])];
	if (files.length && composer.value) composer.value.addFiles(files);
}

watch(() => props.channel, open, { immediate: true });

// join/leave/add notices arrive as system messages; refresh the member list when one lands
watch(
	() => convo.value.messages.at(-1),
	(last, previous) => {
		if (last && previous && last !== previous && last.message_type === "System") loadDetails();
	}
);

// keep the pinned counter in sync with pin/unpin updates
watch(
	() => convo.value.messages.filter((m) => m.is_pinned && !m.is_deleted).length,
	(count, old) => {
		if (details.value && old !== undefined && count !== old) loadDetails();
	}
);

onBeforeUnmount(() => {
	chat.activeChannel = null;
	chat.activeThread = null;
});
</script>

<style scoped>
.header-btn {
	display: flex;
	align-items: center;
	gap: 0.25rem;
	border-radius: 0.25rem;
	padding: 0.25rem 0.5rem;
	font-size: 0.8125rem;
	color: var(--ink-gray-6, #6b7280);
}
.header-btn:hover {
	background: var(--surface-gray-2, #f3f3f3);
}
</style>
