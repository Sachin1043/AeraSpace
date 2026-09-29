<template>
	<div class="relative inline-flex shrink-0">
		<Avatar :label="info.full_name" :image="info.user_image" :size="size" />
		<PresenceDot
			v-if="showPresence"
			:status="chat.statusOf(user)"
			:size="dotSize"
			:border="2"
			class="absolute -bottom-px -right-px"
		/>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { Avatar } from "frappe-ui";
import { useChat } from "@/stores/chat";
import PresenceDot from "./PresenceDot.vue";

const props = defineProps({
	user: { type: String, required: true },
	size: { type: String, default: "md" },
	showPresence: { type: Boolean, default: true },
});

const chat = useChat();
const info = computed(() => chat.person(props.user));
// keep the dot proportional to the avatar, like a corner badge
const dotSize = computed(
	() =>
		({ xs: "xs", sm: "sm", md: "sm", lg: "md", xl: "md", "2xl": "lg", "3xl": "xl" }[
			props.size
		] || "md")
);
</script>
