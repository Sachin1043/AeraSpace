<template>
	<div
		v-if="meeting"
		class="fixed right-4 top-14 z-50 w-80 rounded-xl border bg-surface-modal p-4 shadow-xl"
		role="alertdialog"
		aria-label="Meeting reminder"
	>
		<div class="flex items-start gap-3">
			<div
				class="flex size-9 shrink-0 items-center justify-center rounded-full bg-surface-blue-2"
			>
				<LucideCalendarClock class="size-4 text-ink-blue-3" />
			</div>
			<div class="min-w-0 flex-1">
				<div class="truncate text-base font-semibold text-ink-gray-9">
					{{ meeting.title }}
				</div>
				<div class="text-sm text-ink-gray-5">
					{{ when }} · {{ fromSite(meeting.starts_at).format("h:mm A") }} ·
					{{ meeting.duration }} min
				</div>
			</div>
		</div>
		<div class="mt-4 flex gap-2">
			<Button class="flex-1" @click="meetings.reminder = null">Dismiss</Button>
			<Button
				class="flex-1"
				variant="solid"
				theme="green"
				:loading="calls.busy"
				@click="join"
			>
				<template #prefix><LucideVideo class="size-4" /></template>
				Join
			</Button>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { Button } from "frappe-ui";
import { useCall } from "@/stores/call";
import { useMeetings } from "@/stores/meetings";
import { fromSite } from "@/utils/siteTime";
import { now } from "@/utils/now";
import LucideCalendarClock from "~icons/lucide/calendar-clock";
import LucideVideo from "~icons/lucide/video";

const meetings = useMeetings();
const calls = useCall();
// nothing to remind about once I'm already in its call
const meeting = computed(() => {
	const m = meetings.reminder;
	return m && calls.active?.channel !== m.channel ? m : null;
});

const when = computed(() => {
	const minutes = Math.ceil((fromSite(meeting.value.starts_at).valueOf() - now.value) / 60000);
	return minutes > 0 ? `Starts in ${minutes} min` : "Starting now";
});

function join() {
	const m = meeting.value;
	meetings.reminder = null;
	calls.start(m.channel, m.call_type);
}
</script>
