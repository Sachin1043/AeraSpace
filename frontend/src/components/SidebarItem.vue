<template>
	<router-link
		:to="{ name: 'Conversation', params: { channel: channel.name } }"
		class="flex items-center gap-2 rounded px-2 py-1 text-base hover:bg-surface-gray-3"
		:class="[
			active
				? 'bg-surface-white text-ink-gray-9 shadow-sm'
				: muted
				? 'text-ink-gray-4'
				: 'text-ink-gray-7',
			channel.unread && !active && !muted ? 'font-semibold text-ink-gray-9' : '',
		]"
	>
		<span class="flex w-4 shrink-0 items-center justify-center text-ink-gray-5">
			<slot name="icon" />
		</span>
		<span class="min-w-0 flex-1 truncate">{{ chat.channelTitle(channel) }}</span>
		<LucideBellOff v-if="muted" class="size-3 shrink-0 text-ink-gray-4" />
		<span
			v-else-if="channel.unread && !active"
			class="rounded-full bg-surface-gray-7 px-1.5 text-xs font-medium leading-5 text-ink-white"
		>
			{{ channel.unread > 99 ? "99+" : channel.unread }}
		</span>
	</router-link>
</template>

<script setup>
import { computed } from "vue";
import { useChat } from "@/stores/chat";
import LucideBellOff from "~icons/lucide/bell-off";

const props = defineProps({
	channel: { type: Object, required: true },
	active: { type: Boolean, default: false },
});
const chat = useChat();
const muted = computed(() => chat.isMuted(props.channel));
</script>
