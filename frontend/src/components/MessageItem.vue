<template>
	<div
		v-if="message.message_type === 'System'"
		class="py-1 pl-14 text-sm italic text-ink-gray-5"
	>
		{{ systemText }} · {{ time(message.creation) }}
	</div>

	<div
		v-else
		class="group relative flex gap-3 rounded px-2"
		:class="[
			compact ? 'py-0.5' : 'mt-2 pb-0.5 pt-1.5',
			message.is_pinned && !inThread
				? 'bg-surface-amber-1'
				: mentionsMe
				? 'bg-surface-blue-1 hover:bg-surface-blue-2'
				: isMine
				? 'bg-surface-gray-1 hover:bg-surface-gray-2'
				: 'hover:bg-surface-gray-1',
			highlighted ? 'ring-2 ring-outline-amber-2' : '',
		]"
	>
		<div class="w-8 shrink-0">
			<button
				v-if="!compact"
				class="block"
				title="View profile"
				@click="chat.viewProfile(message.sender)"
			>
				<UserAvatar :user="message.sender" size="lg" :show-presence="false" />
			</button>
			<span
				v-else
				class="invisible block pt-0.5 text-right text-2xs text-ink-gray-4 group-hover:visible"
			>
				{{ time(message.creation, "h:mm") }}
			</span>
		</div>

		<div class="min-w-0 flex-1">
			<div v-if="!compact" class="flex items-baseline gap-2">
				<button
					class="text-base font-semibold text-ink-gray-9 hover:underline"
					@click="chat.viewProfile(message.sender)"
				>
					{{ chat.displayName(message.sender) }}
				</button>
				<span class="text-xs text-ink-gray-5">{{ time(message.creation) }}</span>
				<span
					v-if="message.is_pinned && !inThread"
					class="flex items-center gap-0.5 text-xs text-ink-amber-3"
				>
					<LucidePin class="size-3" /> Pinned
				</span>
			</div>

			<!-- quoted reply -->
			<div
				v-if="message.reply_to && !message.is_deleted"
				class="mb-1 mt-0.5 border-l-2 border-outline-gray-3 pl-2 text-sm text-ink-gray-6"
			>
				<span class="font-medium text-ink-gray-7">{{
					chat.displayName(message.reply_to.sender)
				}}</span>
				<span v-if="message.reply_to.is_deleted" class="italic"> · message deleted</span>
				<span v-else class="line-clamp-2">
					{{ plainText(message.reply_to.content, chat.person) || "📎 File" }}</span
				>
			</div>

			<div v-if="message.is_deleted" class="text-base italic text-ink-gray-5">
				This message was deleted.
			</div>

			<!-- editing -->
			<div v-else-if="editing" class="mt-1">
				<textarea
					ref="editInput"
					v-model="draft"
					rows="2"
					class="w-full resize-none rounded border-outline-gray-2 text-base focus:border-outline-gray-4 focus:ring-0"
					@keydown.enter.exact.prevent="saveEdit"
					@keydown.esc="editing = false"
				/>
				<div class="mt-1 flex gap-2 text-xs text-ink-gray-5">
					<span>Enter to save · Esc to cancel</span>
				</div>
			</div>

			<template v-else>
				<div
					v-if="message.content"
					class="message-content break-words text-base leading-relaxed text-ink-gray-8"
					:class="{ 'opacity-50': message.pending, 'text-ink-red-4': message.failed }"
					v-html="html"
				/>
				<span v-if="message.is_edited" class="text-2xs text-ink-gray-4">(edited)</span>
				<div v-if="message.failed" class="text-xs text-ink-red-4">Not sent</div>

				<!-- files -->
				<div v-if="message.files?.length" class="mt-1.5 flex flex-wrap gap-2">
					<template v-for="file in message.files" :key="file.name">
						<button
							v-if="isImage(file)"
							class="overflow-hidden rounded-lg border hover:opacity-90"
							@click="preview = file"
						>
							<img
								:src="file.file_url"
								:alt="file.file_name"
								class="max-h-60 max-w-xs object-cover"
								loading="lazy"
							/>
						</button>
						<a
							v-else
							:href="file.file_url"
							target="_blank"
							class="flex w-64 items-center gap-3 rounded-lg border px-3 py-2 hover:bg-surface-gray-2"
						>
							<div
								class="flex size-9 shrink-0 items-center justify-center rounded bg-surface-gray-3 text-2xs font-semibold uppercase text-ink-gray-7"
							>
								{{ fileExtension(file.file_name) || "file" }}
							</div>
							<div class="min-w-0">
								<div class="truncate text-sm font-medium text-ink-gray-8">
									{{ file.file_name }}
								</div>
								<div class="text-xs text-ink-gray-5">
									{{ formatSize(file.file_size) }}
								</div>
							</div>
						</a>
					</template>
				</div>

				<!-- reactions -->
				<div v-if="reactionList.length" class="mt-1 flex flex-wrap gap-1">
					<button
						v-for="[emoji, users] in reactionList"
						:key="emoji"
						class="flex items-center gap-1 rounded-full border px-2 py-0.5 text-sm"
						:class="
							users.includes(session.user)
								? 'border-outline-blue-1 bg-surface-blue-1 text-ink-blue-3'
								: 'bg-surface-white text-ink-gray-7 hover:bg-surface-gray-2'
						"
						:title="users.map((u) => chat.displayName(u)).join(', ')"
						@click="chat.toggleReaction(message, emoji)"
					>
						{{ emoji }} <span class="text-xs">{{ users.length }}</span>
					</button>
					<EmojiPicker @select="(e) => chat.toggleReaction(message, e)">
						<template #default="{ toggle }">
							<button
								class="rounded-full border px-2 py-0.5 text-ink-gray-5 hover:bg-surface-gray-2"
								@click="toggle"
							>
								<LucideSmilePlus class="size-3.5" />
							</button>
						</template>
					</EmojiPicker>
				</div>

				<!-- thread summary -->
				<button
					v-if="!inThread && message.reply_count"
					class="mt-1 flex items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-surface-white"
					@click="$emit('open-thread', message)"
				>
					<span class="font-medium text-ink-blue-3">
						{{ message.reply_count }}
						{{ message.reply_count === 1 ? "reply" : "replies" }}
					</span>
					<span v-if="message.last_reply_at" class="text-xs text-ink-gray-5"
						>Last reply {{ relative(message.last_reply_at) }}</span
					>
				</button>
			</template>
		</div>

		<!-- hover toolbar -->
		<div
			v-if="!message.is_deleted && !message.pending && !editing"
			class="absolute -top-3 right-3 z-10 hidden items-center rounded-lg border bg-surface-white shadow-sm group-hover:flex"
			:class="{ '!flex': menuOpen }"
		>
			<template v-if="canInteract">
				<button
					v-for="emoji in quickReactions"
					:key="emoji"
					class="px-1.5 py-1 text-base hover:bg-surface-gray-2"
					:title="`React with ${emoji}`"
					@click="chat.toggleReaction(message, emoji)"
				>
					{{ emoji }}
				</button>
				<EmojiPicker
					@select="(e) => chat.toggleReaction(message, e)"
					@toggle="(v) => (menuOpen = v)"
				>
					<template #default="{ toggle }">
						<button
							class="p-1.5 text-ink-gray-6 hover:bg-surface-gray-2"
							title="Add reaction"
							@click="toggle"
						>
							<LucideSmilePlus class="size-4" />
						</button>
					</template>
				</EmojiPicker>
				<button
					v-if="!inThread"
					class="p-1.5 text-ink-gray-6 hover:bg-surface-gray-2"
					title="Reply in thread"
					@click="$emit('open-thread', message)"
				>
					<LucideMessageSquareText class="size-4" />
				</button>
				<button
					v-if="canPostTopLevel || inThread"
					class="p-1.5 text-ink-gray-6 hover:bg-surface-gray-2"
					title="Quote reply"
					@click="$emit('reply', message)"
				>
					<LucideReply class="size-4" />
				</button>
			</template>
			<Dropdown
				:options="moreOptions"
				placement="right"
				@update:open="(v) => (menuOpen = v)"
			>
				<button class="p-1.5 text-ink-gray-6 hover:bg-surface-gray-2" title="More">
					<LucideEllipsis class="size-4" />
				</button>
			</Dropdown>
		</div>

		<Dialog v-model="showPreview" :options="{ size: '5xl' }">
			<template #body>
				<div v-if="preview" class="flex flex-col items-center gap-3 p-4">
					<img
						:src="preview.file_url"
						:alt="preview.file_name"
						class="max-h-[75vh] rounded"
					/>
					<div class="flex items-center gap-3 text-sm text-ink-gray-6">
						{{ preview.file_name }} · {{ formatSize(preview.file_size) }}
						<a
							:href="preview.file_url"
							download
							class="text-ink-blue-3 hover:underline"
							>Download</a
						>
					</div>
				</div>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, nextTick, ref } from "vue";
import { Dialog, Dropdown, dayjsLocal, toast } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { session } from "@/session";
import { fileExtension, formatSize, isImage, renderMarkdown, plainText } from "@/utils/format";
import { mentionsMe as hasMention } from "@/utils/mentions";
import UserAvatar from "./UserAvatar.vue";
import EmojiPicker from "./EmojiPicker.vue";
import LucidePin from "~icons/lucide/pin";
import LucideSmilePlus from "~icons/lucide/smile-plus";
import LucideMessageSquareText from "~icons/lucide/message-square-text";
import LucideReply from "~icons/lucide/reply";
import LucideEllipsis from "~icons/lucide/ellipsis";

const props = defineProps({
	message: { type: Object, required: true },
	compact: Boolean,
	inThread: Boolean,
	canInteract: { type: Boolean, default: true },
	canPostTopLevel: { type: Boolean, default: true },
	isAdmin: Boolean,
	highlighted: Boolean,
});
const emit = defineEmits(["open-thread", "reply", "create-task"]);

const chat = useChat();
const quickReactions = ["👍", "❤️", "😂", "🎉"];
const editing = ref(false);
const draft = ref("");
const editInput = ref(null);
const menuOpen = ref(false);
const preview = ref(null);
const showPreview = computed({
	get: () => !!preview.value,
	set: (v) => !v && (preview.value = null),
});

const html = computed(() =>
	renderMarkdown(props.message.content, { person: chat.person, me: session.user })
);
const mentionsMe = computed(
	() => props.message.sender !== session.user && hasMention(props.message.content, session.user)
);
const reactionList = computed(() =>
	Object.entries(props.message.reactions || {}).filter(([, users]) => users.length)
);
const isMine = computed(() => props.message.sender === session.user);

// notices like "Sachin K S joined" read "You joined" for the person who did it
const systemText = computed(() => {
	const content = props.message.content || "";
	const name = chat.person(props.message.sender).full_name;
	return isMine.value && content.startsWith(name) ? `You${content.slice(name.length)}` : content;
});

function time(creation, format = "h:mm A") {
	return dayjsLocal(creation).format(format);
}

function relative(value) {
	return dayjsLocal(value).fromNow();
}

async function startEdit() {
	draft.value = chat.editableText(props.message);
	editing.value = true;
	await nextTick();
	editInput.value?.focus();
}

async function saveEdit() {
	const content = draft.value.trim();
	if (!content || content === chat.editableText(props.message)) {
		editing.value = false;
		return;
	}
	await chat.editMessage(props.message, content);
	editing.value = false;
}

function copyText() {
	navigator.clipboard?.writeText(chat.editableText(props.message));
	toast.create({ message: "Copied to clipboard", type: "success" });
}

function confirmDelete() {
	if (window.confirm("Delete this message? This cannot be undone."))
		chat.deleteMessage(props.message);
}

const moreOptions = computed(() => {
	const saved = chat.bookmarks.has(props.message.name);
	const options = [
		props.message.content && { label: "Copy text", icon: "copy", onClick: copyText },
		{
			label: saved ? "Remove from saved" : "Save for later",
			icon: "bookmark",
			onClick: () => chat.toggleBookmark(props.message),
		},
	];
	if (props.canInteract && !props.inThread) {
		options.push({
			label: props.message.is_pinned ? "Unpin" : "Pin to channel",
			icon: "map-pin",
			onClick: () => chat.togglePin(props.message),
		});
	}
	if (props.canInteract && props.message.message_type !== "System") {
		options.push({
			label: "Create task",
			icon: "check-square",
			onClick: () => emit("create-task", props.message),
		});
	}
	if (isMine.value) options.push({ label: "Edit", icon: "edit-2", onClick: startEdit });
	if (isMine.value || props.isAdmin)
		options.push({ label: "Delete", icon: "trash-2", onClick: confirmDelete });
	return options.filter(Boolean);
});
</script>

<style scoped>
.message-content :deep(p) {
	margin: 0;
}
.message-content :deep(p + p) {
	margin-top: 0.4rem;
}
.message-content :deep(a) {
	color: var(--ink-blue-3);
	text-decoration: underline;
}
.message-content :deep(code) {
	border-radius: 4px;
	background: var(--surface-gray-2, #f3f3f3);
	padding: 0.1rem 0.3rem;
	font-size: 0.85em;
}
.message-content :deep(pre) {
	margin: 0.35rem 0;
	overflow-x: auto;
	border-radius: 6px;
	background: #1f2937;
	padding: 0.6rem 0.8rem;
	color: #f9fafb;
}
.message-content :deep(pre code) {
	background: transparent;
	padding: 0;
	color: inherit;
}
.message-content :deep(ul) {
	list-style: disc;
	padding-left: 1.25rem;
}
.message-content :deep(ol) {
	list-style: decimal;
	padding-left: 1.25rem;
}
.message-content :deep(.mention) {
	border-radius: 4px;
	background: var(--surface-blue-2);
	padding: 0 0.2rem;
	font-weight: 500;
	color: var(--ink-blue-3);
}
.message-content :deep(.mention-me) {
	background: var(--surface-amber-2);
	color: var(--ink-amber-3);
}
.message-content :deep(blockquote) {
	border-left: 3px solid var(--outline-gray-3);
	padding-left: 0.6rem;
	color: var(--ink-gray-6);
}
</style>
