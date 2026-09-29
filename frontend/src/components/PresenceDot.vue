<template>
	<span
		class="inline-flex shrink-0 items-center justify-center rounded-full"
		:class="[colors[status], sizes[size]]"
		:style="border ? { boxShadow: `0 0 0 ${border}px var(--${borderColor})` } : null"
		:title="STATUS_LABELS[status]"
	>
		<!-- do not disturb: red with a white bar, like a no-entry sign -->
		<span v-if="status === 'dnd'" class="h-[18%] w-[55%] rounded-full bg-white" />
	</span>
</template>

<script setup>
import { STATUS_LABELS } from "@/stores/chat";

defineProps({
	status: { type: String, default: "offline" },
	size: { type: String, default: "md" },
	border: { type: Number, default: 0 }, // ring in the background colour, so the dot sits cleanly on an avatar
	borderColor: { type: String, default: "surface-white" },
});

const colors = {
	online: "bg-[#2ecc71]",
	away: "bg-[#f5b400]",
	busy: "bg-[#e8352e]",
	dnd: "bg-[#e8352e]",
	invisible: "border-2 border-[#a3a3a3] bg-transparent",
	offline: "bg-[#a3a3a3]",
};
const sizes = { xs: "size-1.5", sm: "size-2", md: "size-2.5", lg: "size-3", xl: "size-3.5" };
</script>
