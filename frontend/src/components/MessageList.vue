<template>
	<div ref="scroller" class="overflow-y-auto px-4 pt-4" @scroll="onScroll">
		<div v-if="loading && hasMore" class="flex justify-center py-2">
			<LoadingIndicator class="size-4" />
		</div>
		<!-- shown only until the first real message; system notices don't count -->
		<div v-if="showIntro" class="mb-6 mt-8 px-2">
			<button
				v-if="greeting"
				class="inline-flex items-center gap-2 rounded-lg border px-3 py-1.5 text-lg font-semibold text-ink-gray-9 hover:border-outline-gray-3 hover:bg-surface-gray-2"
				:title="`Send “${greeting}”`"
				@click="$emit('say-hello', greeting)"
			>
				👋 Say hello
			</button>
			<div v-else class="text-lg font-semibold text-ink-gray-9">👋 Say hello</div>
			<div class="mt-1 text-base text-ink-gray-6">{{ intro }}</div>
		</div>

		<template v-for="row in rows" :key="row.key">
			<div v-if="row.type === 'date'" class="my-4 flex items-center gap-3">
				<div class="h-px flex-1 bg-outline-gray-2" />
				<span class="text-xs font-medium text-ink-gray-5">{{ row.label }}</span>
				<div class="h-px flex-1 bg-outline-gray-2" />
			</div>
			<MessageItem
				v-else
				:id="`message-${row.message.name}`"
				:message="row.message"
				:compact="row.compact"
				:in-thread="inThread"
				:can-interact="canInteract"
				:can-post-top-level="canPostTopLevel"
				:is-admin="isAdmin"
				:highlighted="row.message.name === highlight"
				:readers="readers"
				@open-thread="(m) => $emit('open-thread', m)"
				@reply="(m) => $emit('reply', m)"
				@create-task="(m) => $emit('create-task', m)"
			/>
		</template>
		<div class="h-4" />
	</div>
</template>

<script setup>
import { computed, nextTick, onMounted, ref, watch } from "vue";
import { LoadingIndicator, dayjsLocal } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { session } from "@/session";
import MessageItem from "./MessageItem.vue";

const props = defineProps({
	channel: { type: String, required: true },
	messages: { type: Array, required: true },
	hasMore: Boolean,
	loading: Boolean,
	intro: String,
	greeting: String, // message the "Say hello" button sends; empty = not clickable
	readers: { type: Array, default: () => [] }, // for read receipts on my messages
	inThread: Boolean,
	canInteract: { type: Boolean, default: true },
	canPostTopLevel: { type: Boolean, default: true },
	isAdmin: Boolean,
	highlight: String,
});
defineEmits(["open-thread", "reply", "create-task", "say-hello"]);

// once anyone has written (even if it was later deleted) the conversation has started
const showIntro = computed(
	() =>
		!props.hasMore && !!props.intro && !props.messages.some((m) => m.message_type !== "System")
);

const chat = useChat();
const scroller = ref(null);
const GROUP_WINDOW_MINUTES = 5;

function dateLabel(day) {
	const today = dayjsLocal().startOf("day");
	if (day.isSame(today, "day")) return "Today";
	if (day.isSame(today.subtract(1, "day"), "day")) return "Yesterday";
	return day.format(day.year() === today.year() ? "dddd, MMMM D" : "MMMM D, YYYY");
}

const rows = computed(() => {
	const result = [];
	let previous = null;
	for (const message of props.messages) {
		const at = dayjsLocal(message.creation);
		if (!previous || !at.isSame(previous.at, "day")) {
			result.push({
				type: "date",
				key: `date-${at.format("YYYY-MM-DD")}`,
				label: dateLabel(at.startOf("day")),
			});
			previous = null;
		}
		const compact =
			previous &&
			previous.message.message_type !== "System" &&
			message.message_type !== "System" &&
			previous.message.sender === message.sender &&
			!message.reply_to &&
			at.diff(previous.at, "minute") < GROUP_WINDOW_MINUTES;
		result.push({ type: "message", key: message.client_id || message.name, message, compact });
		previous = { message, at };
	}
	return result;
});

// ---- scrolling -------------------------------------------------------

function isNearBottom() {
	const el = scroller.value;
	return el && el.scrollHeight - el.scrollTop - el.clientHeight < 150;
}

function scrollToBottom() {
	const el = scroller.value;
	if (el) el.scrollTop = el.scrollHeight;
}

async function onScroll() {
	const el = scroller.value;
	if (props.inThread || !el || el.scrollTop > 80 || !props.hasMore || props.loading) return;
	const previousHeight = el.scrollHeight;
	const loaded = await chat.loadOlder(props.channel);
	if (loaded) {
		await nextTick();
		el.scrollTop = el.scrollHeight - previousHeight; // keep the reader's position
	}
}

watch(
	() => props.messages.length,
	async (length, oldLength) => {
		const last = props.messages[length - 1];
		const appended = length > oldLength && last && props.messages[oldLength - 1] !== last;
		if (!appended) return;
		const stick = isNearBottom() || last.sender === session.user;
		await nextTick();
		if (stick) scrollToBottom();
	}
);

async function scrollToMessage(name) {
	await nextTick();
	document.getElementById(`message-${name}`)?.scrollIntoView({ block: "center" });
}

onMounted(async () => {
	await nextTick();
	if (props.highlight) scrollToMessage(props.highlight);
	else scrollToBottom();
});

defineExpose({ scrollToBottom, scrollToMessage });
</script>
