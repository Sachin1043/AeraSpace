<template>
	<div class="mx-auto max-w-3xl px-6 py-8">
		<h1 class="text-xl font-semibold text-ink-gray-9">Saved items</h1>
		<p class="text-base text-ink-gray-6">
			Messages you saved for later. Only you can see this list.
		</p>

		<div v-if="saved.loading && !saved.data" class="flex justify-center py-10">
			<LoadingIndicator class="size-5" />
		</div>
		<div
			v-else-if="!saved.data?.length"
			class="mt-6 rounded-lg border px-4 py-10 text-center text-base text-ink-gray-5"
		>
			Nothing saved yet. Use “Save for later” from any message's ⋯ menu.
		</div>
		<div v-else class="mt-6 space-y-2">
			<div
				v-for="message in saved.data"
				:key="message.name"
				class="rounded-lg border p-3 hover:bg-surface-gray-1"
			>
				<button class="block w-full text-left" @click="open(message)">
					<div class="flex items-baseline gap-2 text-xs text-ink-gray-5">
						<span>⭐ {{ where(message) }}</span>
						<span>· {{ dayjsLocal(message.creation).format("MMM D, h:mm A") }}</span>
					</div>
					<div class="mt-1 text-sm font-semibold text-ink-gray-9">
						{{ chat.displayName(message.sender) }}
					</div>
					<div class="line-clamp-3 text-base text-ink-gray-8">
						{{
							plainText(message.content, chat.person) ||
							"📎 " + message.files.map((f) => f.file_name).join(", ")
						}}
					</div>
				</button>
				<div class="mt-2 flex justify-end">
					<Button size="sm" variant="ghost" @click="remove(message)">Remove</Button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { Button, LoadingIndicator, createResource, dayjsLocal } from "frappe-ui";
import { useRouter } from "vue-router";
import { useChat } from "@/stores/chat";
import { plainText } from "@/utils/format";

const chat = useChat();
const router = useRouter();
const saved = createResource({ url: "aeraspace.api.chat.get_bookmarks", auto: true });

function where(message) {
	if (["Public", "Private", "Announcement"].includes(message.channel_type))
		return `#${message.channel_name}`;
	const entry = chat.sidebarEntry(message.channel);
	return entry ? chat.channelTitle(entry) : "Conversation";
}

function open(message) {
	const query = message.thread_root
		? { thread: message.thread_root }
		: { message: message.name };
	router.push({ name: "Conversation", params: { channel: message.channel }, query });
}

async function remove(message) {
	await chat.toggleBookmark(message);
	saved.reload();
}
</script>
