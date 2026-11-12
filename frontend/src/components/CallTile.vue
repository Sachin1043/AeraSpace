<template>
	<div
		class="relative flex items-center justify-center overflow-hidden rounded-lg bg-surface-gray-3"
	>
		<video
			v-show="stream && camera"
			ref="video"
			autoplay
			playsinline
			muted
			class="h-full w-full"
			:class="[
				sharing ? 'object-contain' : 'object-cover',
				{ '-scale-x-100': self && !sharing },
			]"
		/>
		<UserAvatar
			v-if="!(stream && camera)"
			:user="user"
			:size="compact ? 'lg' : '3xl'"
			:show-presence="false"
		/>
		<!-- other people's voice; my own tile stays silent -->
		<audio v-if="!self" ref="audio" autoplay />
		<div
			class="absolute bottom-1.5 left-1.5 flex max-w-[85%] items-center gap-1 rounded bg-black/55 px-1.5 py-0.5 text-xs text-white"
		>
			<LucideMicOff v-if="muted" class="size-3 shrink-0 text-red-300" />
			<LucideMonitorUp v-if="sharing" class="size-3 shrink-0" />
			<span class="truncate">{{ self ? "You" : chat.person(user).full_name }}</span>
			<span v-if="!self && !connected" class="shrink-0 text-white/70">· connecting…</span>
		</div>
	</div>
</template>

<script setup>
import { onMounted, ref, watch } from "vue";
import { useChat } from "@/stores/chat";
import UserAvatar from "./UserAvatar.vue";
import LucideMicOff from "~icons/lucide/mic-off";
import LucideMonitorUp from "~icons/lucide/monitor-up";

const props = defineProps({
	user: { type: String, required: true },
	stream: { type: Object, default: null },
	self: { type: Boolean, default: false },
	camera: { type: Boolean, default: false },
	muted: { type: Boolean, default: false },
	sharing: { type: Boolean, default: false },
	connected: { type: Boolean, default: true },
	compact: { type: Boolean, default: false },
});

const chat = useChat();
const video = ref(null);
const audio = ref(null);

function attach() {
	if (video.value && video.value.srcObject !== props.stream)
		video.value.srcObject = props.stream;
	if (audio.value && audio.value.srcObject !== props.stream)
		audio.value.srcObject = props.stream;
}
onMounted(attach);
watch(() => props.stream, attach);
</script>
