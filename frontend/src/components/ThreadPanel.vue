<template>
	<aside class="flex h-full w-[26rem] shrink-0 flex-col border-l bg-surface-white">
		<header class="flex h-12 shrink-0 items-center gap-2 border-b px-4">
			<div class="min-w-0 flex-1">
				<div class="text-base font-semibold text-ink-gray-9">Thread</div>
				<div class="truncate text-xs text-ink-gray-5">{{ channelTitle }}</div>
			</div>
			<Button
				size="sm"
				:variant="data.isFollowing ? 'subtle' : 'outline'"
				@click="chat.toggleFollow(root)"
			>
				{{ data.isFollowing ? "Following" : "Follow" }}
			</Button>
			<Button variant="ghost" size="sm" @click="$emit('close')"
				><LucideX class="size-4"
			/></Button>
		</header>

		<template v-if="data.loaded">
			<MessageList
				ref="list"
				:channel="channel"
				:messages="messages"
				:in-thread="true"
				:can-interact="canInteract"
				:is-admin="isAdmin"
				class="flex-1"
				@create-task="(m) => emit('create-task', m)"
			/>
			<div class="shrink-0 px-3 pb-3">
				<div class="h-5 text-xs text-ink-gray-5">{{ typingText }}</div>
				<Composer
					v-if="canInteract"
					:key="root"
					:channel="channel"
					placeholder="Reply…"
					:members="members"
					@send="
						(m) => chat.send(channel, m.content, { files: m.files, threadRoot: root })
					"
					@typing="chat.notifyTyping(channel, root)"
				/>
				<div
					v-else
					class="rounded border bg-surface-gray-1 px-3 py-2 text-sm text-ink-gray-6"
				>
					Join the channel to reply.
				</div>
			</div>
		</template>
		<div v-else class="flex flex-1 items-center justify-center">
			<LoadingIndicator class="size-5" />
		</div>
	</aside>
</template>

<script setup>
import { computed, watch } from "vue";
import { Button, LoadingIndicator } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import MessageList from "./MessageList.vue";
import Composer from "./Composer.vue";
import LucideX from "~icons/lucide/x";

const props = defineProps({
	root: { type: String, required: true },
	channel: { type: String, required: true },
	channelTitle: String,
	canInteract: Boolean,
	isAdmin: Boolean,
	typingNames: Function,
	members: { type: Array, default: () => [] },
});
const emit = defineEmits(["close", "create-task"]);
const chat = useChat();

const data = computed(() => chat.thread(props.root));
const messages = computed(() => (data.value.root ? [data.value.root, ...data.value.replies] : []));
const typingText = computed(
	() => props.typingNames?.(chat.typingUsers(props.channel, props.root)) || ""
);

watch(
	() => props.root,
	async (root) => {
		chat.activeThread = root;
		try {
			await chat.loadThread(root);
		} catch (error) {
			showError(error);
			emit("close");
		}
	},
	{ immediate: true }
);
</script>
