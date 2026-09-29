<template>
	<Popover :placement="placement" @update:show="(v) => emit('toggle', v)">
		<template #target="{ togglePopover, isOpen }">
			<slot :toggle="togglePopover" :is-open="isOpen" />
		</template>
		<template #body-main="{ close }">
			<div class="w-72 p-2">
				<div v-for="group in groups" :key="group.label" class="mb-1">
					<div class="px-1 pb-1 text-2xs font-medium uppercase text-ink-gray-5">
						{{ group.label }}
					</div>
					<div class="grid grid-cols-8">
						<button
							v-for="emoji in group.emojis"
							:key="emoji"
							class="rounded p-1 text-lg leading-none hover:bg-surface-gray-3"
							@click="
								emit('select', emoji);
								close();
							"
						>
							{{ emoji }}
						</button>
					</div>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup>
import { Popover } from "frappe-ui";

defineProps({ placement: { type: String, default: "top-end" } });
const emit = defineEmits(["select", "toggle"]);

const groups = [
	{
		label: "Reactions",
		emojis: [
			"👍",
			"👎",
			"❤️",
			"😂",
			"🎉",
			"🙏",
			"👀",
			"🔥",
			"✅",
			"❌",
			"💯",
			"🚀",
			"👏",
			"🙌",
			"🤝",
			"⭐",
		],
	},
	{
		label: "Smileys",
		emojis: [
			"😀",
			"😄",
			"😅",
			"😊",
			"😉",
			"😍",
			"🤔",
			"😮",
			"😢",
			"😡",
			"😴",
			"🤯",
			"🥳",
			"😎",
			"🙂",
			"🙃",
		],
	},
	{
		label: "Work",
		emojis: [
			"💻",
			"🐛",
			"🛠️",
			"📌",
			"📎",
			"📅",
			"⏳",
			"⚠️",
			"✍️",
			"📝",
			"📦",
			"🔒",
			"☕",
			"🍴",
			"🏠",
			"🏖️",
		],
	},
];
</script>
