<template>
	<div
		class="rounded-lg border bg-surface-white focus-within:border-outline-gray-4 focus-within:shadow-sm"
		@paste="onPaste"
	>
		<!-- replying to -->
		<div v-if="replyTo" class="flex items-start gap-2 border-b px-3 py-2 text-sm">
			<LucideReply class="mt-0.5 size-3.5 shrink-0 text-ink-gray-5" />
			<div class="min-w-0 flex-1">
				<span class="font-medium text-ink-gray-7"
					>Replying to {{ chat.displayName(replyTo.sender) }}</span
				>
				<div class="truncate text-ink-gray-5">{{ replyTo.content || "📎 File" }}</div>
			</div>
			<button class="text-ink-gray-5 hover:text-ink-gray-8" @click="$emit('cancel-reply')">
				<LucideX class="size-4" />
			</button>
		</div>

		<!-- attachments -->
		<div v-if="uploads.length" class="flex flex-wrap gap-2 px-3 pt-2">
			<div
				v-for="upload in uploads"
				:key="upload.id"
				class="relative flex w-48 items-center gap-2 rounded border bg-surface-gray-1 px-2 py-1.5"
			>
				<img
					v-if="upload.preview"
					:src="upload.preview"
					class="size-8 shrink-0 rounded object-cover"
				/>
				<LucideFile v-else class="size-5 shrink-0 text-ink-gray-5" />
				<div class="min-w-0 flex-1">
					<div class="truncate text-xs text-ink-gray-8">{{ upload.file.name }}</div>
					<div
						class="text-2xs"
						:class="upload.error ? 'text-ink-red-4' : 'text-ink-gray-5'"
					>
						{{
							upload.error ||
							(upload.result
								? formatSize(upload.file.size)
								: `Uploading ${upload.progress}%`)
						}}
					</div>
				</div>
				<button class="text-ink-gray-5 hover:text-ink-gray-8" @click="remove(upload)">
					<LucideX class="size-3.5" />
				</button>
			</div>
		</div>

		<div class="relative">
			<!-- @mention suggestions -->
			<div
				v-if="suggestions.length"
				class="absolute bottom-full left-2 z-20 mb-1 w-72 overflow-hidden rounded-lg border bg-surface-white py-1 shadow-lg"
			>
				<button
					v-for="(option, index) in suggestions"
					:key="option.user"
					class="flex w-full items-center gap-2 px-3 py-1.5 text-left"
					:class="
						index === activeSuggestion
							? 'bg-surface-gray-2'
							: 'hover:bg-surface-gray-1'
					"
					@mousedown.prevent="pickMention(option)"
				>
					<UserAvatar v-if="option.user !== '@channel'" :user="option.user" size="sm" />
					<LucideMegaphone v-else class="size-4 text-ink-gray-6" />
					<span class="truncate text-base text-ink-gray-9">{{ option.full_name }}</span>
					<span class="ml-auto truncate text-xs text-ink-gray-5">{{ option.hint }}</span>
				</button>
			</div>
			<textarea
				ref="input"
				v-model="text"
				rows="1"
				class="block max-h-48 w-full resize-none border-0 bg-transparent px-3 py-2.5 text-base text-ink-gray-9 placeholder-ink-gray-4 focus:ring-0"
				:placeholder="placeholder"
				@keydown="onKeydown"
				@input="onInput"
				@click="updateMention"
				@keyup="rememberCaret"
				@blur="
					rememberCaret();
					mention = null;
				"
			/>
		</div>
		<div class="flex items-center justify-between px-2 pb-2">
			<div class="flex items-center gap-1">
				<button
					v-if="allowFiles"
					class="rounded p-1.5 text-ink-gray-6 hover:bg-surface-gray-2"
					title="Attach files"
					@click="picker.click()"
				>
					<LucidePaperclip class="size-4" />
				</button>
				<input ref="picker" type="file" multiple class="hidden" @change="onPick" />
				<EmojiPicker placement="top-start" @select="insertEmoji">
					<template #default="{ toggle }">
						<button
							class="rounded p-1.5 text-ink-gray-6 hover:bg-surface-gray-2"
							title="Insert emoji"
							@mousedown.prevent
							@click="toggle"
						>
							<LucideSmile class="size-4" />
						</button>
					</template>
				</EmojiPicker>
				<span class="text-2xs text-ink-gray-4"
					>@ to mention · **bold** _italic_ `code` · Shift + Enter for a new line</span
				>
			</div>
			<Button variant="solid" size="sm" :disabled="!canSend" @click="send">
				<LucideSendHorizontal class="size-4" />
			</Button>
		</div>
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { Button } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { formatSize } from "@/utils/format";
import LucideSendHorizontal from "~icons/lucide/send-horizontal";
import LucidePaperclip from "~icons/lucide/paperclip";
import LucideFile from "~icons/lucide/file";
import LucideReply from "~icons/lucide/reply";
import LucideX from "~icons/lucide/x";
import LucideMegaphone from "~icons/lucide/megaphone";
import UserAvatar from "./UserAvatar.vue";
import EmojiPicker from "./EmojiPicker.vue";
import LucideSmile from "~icons/lucide/smile";

const props = defineProps({
	channel: { type: String, required: true },
	placeholder: { type: String, default: "Write a message" },
	replyTo: { type: Object, default: null },
	autofocus: { type: Boolean, default: true },
	members: { type: Array, default: () => [] }, // users suggested first for @mentions
	allowFiles: { type: Boolean, default: true },
});
const emit = defineEmits(["send", "typing", "cancel-reply"]);

const chat = useChat();
const text = ref("");
const input = ref(null);
const picker = ref(null);
const uploads = ref([]);
let uploadId = 0;

const uploading = computed(() => uploads.value.some((u) => !u.result && !u.error));
const ready = computed(() => uploads.value.filter((u) => u.result));
const canSend = computed(() => !uploading.value && (text.value.trim() || ready.value.length));

function autosize() {
	const el = input.value;
	if (!el) return;
	el.style.height = "auto";
	el.style.height = `${el.scrollHeight}px`;
}

function onInput() {
	autosize();
	updateMention();
	if (text.value.trim()) emit("typing");
}

// insert at the caret (or replace the selection), keeping focus in the box
let caret = { start: null, end: null };
function rememberCaret() {
	const el = input.value;
	if (el) caret = { start: el.selectionStart, end: el.selectionEnd };
}

async function insertEmoji(emoji) {
	const el = input.value;
	const start = caret.start ?? text.value.length;
	const end = caret.end ?? start;
	text.value = text.value.slice(0, start) + emoji + text.value.slice(end);
	const position = start + emoji.length;
	caret = { start: position, end: position };
	await nextTick();
	el?.focus();
	el?.setSelectionRange(position, position);
	autosize();
}

// ---- @mentions ---------------------------------------------------------

const mention = ref(null); // { start, query }
const activeSuggestion = ref(0);

function updateMention() {
	const el = input.value;
	if (!el) return;
	const before = text.value.slice(0, el.selectionStart);
	const match = before.match(/(?:^|\s)@([\w .'-]{0,30})$/);
	mention.value = match
		? { start: el.selectionStart - match[1].length - 1, query: match[1].toLowerCase() }
		: null;
	activeSuggestion.value = 0;
}

const suggestions = computed(() => {
	if (!mention.value) return [];
	const q = mention.value.query.trim();
	const memberSet = new Set(props.members);
	const people = chat.peopleList
		.filter(
			(p) =>
				!q || p.full_name.toLowerCase().includes(q) || p.user.toLowerCase().startsWith(q)
		)
		.sort((a, b) => Number(memberSet.has(b.user)) - Number(memberSet.has(a.user)))
		.slice(0, 6)
		.map((p) => ({
			user: p.user,
			full_name: p.full_name,
			hint: memberSet.has(p.user) ? p.designation || "" : "not in this conversation",
		}));
	const everyone = "channel".startsWith(q)
		? [{ user: "@channel", full_name: "@channel", hint: "Notify everyone here" }]
		: [];
	return [...people, ...everyone];
});

async function pickMention(option) {
	const el = input.value;
	const end = el.selectionStart;
	const label = option.user === "@channel" ? "@channel" : `@${option.full_name}`;
	text.value = `${text.value.slice(0, mention.value.start)}${label} ${text.value.slice(end)}`;
	const caret = mention.value.start + label.length + 1;
	mention.value = null;
	await nextTick();
	el.setSelectionRange(caret, caret);
	el.focus();
	autosize();
}

function onKeydown(event) {
	if (suggestions.value.length) {
		if (event.key === "ArrowDown" || event.key === "ArrowUp") {
			event.preventDefault();
			const step = event.key === "ArrowDown" ? 1 : -1;
			activeSuggestion.value =
				(activeSuggestion.value + step + suggestions.value.length) %
				suggestions.value.length;
			return;
		}
		if ((event.key === "Enter" || event.key === "Tab") && !event.shiftKey) {
			event.preventDefault();
			pickMention(suggestions.value[activeSuggestion.value]);
			return;
		}
		if (event.key === "Escape") {
			mention.value = null;
			return;
		}
	}
	if (event.key === "Enter" && !event.shiftKey) {
		event.preventDefault();
		send();
	} else if (event.key === "Escape") {
		emit("cancel-reply");
	}
}

function addFiles(fileList) {
	if (!props.allowFiles) return;
	for (const file of fileList) {
		const upload = {
			id: ++uploadId,
			file,
			progress: 0,
			result: null,
			error: null,
			preview: file.type.startsWith("image/") ? URL.createObjectURL(file) : null,
		};
		uploads.value.push(upload);
		const entry = uploads.value.at(-1); // reactive proxy
		chat.uploadFile(props.channel, file, (p) => (entry.progress = p))
			.then((result) => (entry.result = result))
			.catch((error) => (entry.error = error.message));
	}
	input.value?.focus();
}

function remove(upload) {
	if (upload.preview) URL.revokeObjectURL(upload.preview);
	uploads.value = uploads.value.filter((u) => u.id !== upload.id);
}

function onPick(event) {
	addFiles(event.target.files);
	event.target.value = "";
}

function onPaste(event) {
	if (!props.allowFiles) return;
	const files = [...(event.clipboardData?.files || [])];
	if (files.length) {
		event.preventDefault();
		addFiles(files);
	}
}

async function send() {
	if (!canSend.value) return;
	emit("send", { content: text.value, files: ready.value.map((u) => u.result) });
	text.value = "";
	uploads.value.forEach((u) => u.preview && URL.revokeObjectURL(u.preview));
	uploads.value = [];
	await nextTick();
	autosize();
}

watch(
	() => props.replyTo,
	(value) => value && input.value?.focus()
);

onMounted(() => props.autofocus && input.value?.focus());
defineExpose({ addFiles, focus: () => input.value?.focus() });
</script>
