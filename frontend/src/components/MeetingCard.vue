<template>
	<div
		class="rounded-lg border p-3"
		:class="{
			'opacity-60': meeting.status === 'Cancelled',
			'border-green-600/60': meeting.live,
		}"
	>
		<div class="flex items-start gap-3">
			<!-- time -->
			<div class="w-20 shrink-0 text-right">
				<div class="text-base font-semibold tabular-nums text-ink-gray-9">
					{{ start.format("h:mm A") }}
				</div>
				<div class="text-xs tabular-nums text-ink-gray-5">{{ durationLabel }}</div>
			</div>

			<div class="min-w-0 flex-1 border-l pl-3">
				<div class="flex flex-wrap items-center gap-2">
					<component
						:is="meeting.call_type === 'Audio' ? LucidePhone : LucideVideo"
						class="size-4 text-ink-gray-6"
					/>
					<span
						class="text-base font-semibold text-ink-gray-9"
						:class="{ 'line-through': meeting.status === 'Cancelled' }"
					>
						{{ meeting.title }}
					</span>
					<span
						v-if="meeting.live"
						class="flex items-center gap-1 rounded-full bg-surface-green-2 px-2 py-0.5 text-xs font-medium text-ink-green-3"
					>
						<span class="size-1.5 animate-pulse rounded-full bg-green-500" /> Live now
					</span>
					<span
						v-else-if="meeting.status === 'Cancelled'"
						class="rounded-full bg-surface-red-2 px-2 py-0.5 text-xs font-medium text-ink-red-4"
					>
						Cancelled
					</span>
					<span
						v-else-if="startsSoon"
						class="rounded-full bg-surface-amber-2 px-2 py-0.5 text-xs font-medium text-ink-amber-3"
					>
						{{ startsIn }}
					</span>
				</div>
				<div class="mt-0.5 text-sm text-ink-gray-6">
					{{ meeting.is_host ? "You're hosting" : `Hosted by ${meeting.host_name}` }}
					· {{ place }}
				</div>
				<p
					v-if="meeting.agenda"
					class="mt-1.5 line-clamp-3 whitespace-pre-line text-base text-ink-gray-8"
				>
					{{ meeting.agenda }}
				</p>

				<!-- people -->
				<div class="mt-2 flex flex-wrap items-center gap-1.5">
					<div
						v-for="p in people"
						:key="p.user"
						class="relative"
						:title="`${chat.person(p.user).full_name} · ${p.label}`"
					>
						<UserAvatar
							:user="p.user"
							size="sm"
							:show-presence="false"
							:class="{ 'opacity-40': p.response === 'Declined' }"
						/>
						<span
							v-if="p.mark"
							class="absolute -bottom-1 -right-1 flex size-3 items-center justify-center rounded-full text-[8px] text-white ring-2 ring-surface-white"
							:class="p.markClass"
							>{{ p.mark }}</span
						>
					</div>
					<span class="ml-1 text-xs text-ink-gray-5">{{ answerSummary }}</span>
				</div>

				<!-- what happened -->
				<p v-if="past && meeting.call" class="mt-2 text-sm text-ink-gray-6">
					Call lasted {{ callLength }} · {{ meeting.call.joined.length }} joined
				</p>
				<p
					v-else-if="past && meeting.status !== 'Cancelled'"
					class="mt-2 text-sm text-ink-gray-5"
				>
					No call was started.
				</p>
			</div>

			<!-- actions -->
			<div class="flex shrink-0 flex-col items-end gap-2">
				<div class="flex items-center gap-1.5">
					<Button
						v-if="canJoin"
						variant="solid"
						:theme="meeting.live ? 'green' : 'gray'"
						:loading="calls.busy"
						@click="join"
					>
						<template #prefix
							><component
								:is="meeting.call_type === 'Audio' ? LucidePhone : LucideVideo"
								class="size-4"
						/></template>
						{{ meeting.live ? "Join now" : "Join" }}
					</Button>
					<Dropdown :options="menu" placement="right">
						<Button variant="ghost" aria-label="More"
							><LucideEllipsis class="size-4"
						/></Button>
					</Dropdown>
				</div>
				<div
					v-if="!past && !meeting.is_host && meeting.status === 'Scheduled'"
					class="flex items-center gap-1"
				>
					<button
						v-for="r in ['Accepted', 'Declined']"
						:key="r"
						class="rounded px-2 py-0.5 text-xs"
						:class="
							meeting.my_response === r
								? r === 'Accepted'
									? 'bg-surface-green-2 font-medium text-ink-green-3'
									: 'bg-surface-red-2 font-medium text-ink-red-4'
								: 'text-ink-gray-6 hover:bg-surface-gray-2'
						"
						@click="respond(r)"
					>
						{{ r === "Accepted" ? "Going" : "Can't go" }}
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { useRouter } from "vue-router";
import { Button, Dropdown, call, toast } from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { useCall } from "@/stores/call";
import { googleCalendarLink } from "@/stores/meetings";
import { fromSite } from "@/utils/siteTime";
import { formatHours } from "@/utils/clock";
import { now } from "@/utils/now";
import UserAvatar from "./UserAvatar.vue";
import LucideVideo from "~icons/lucide/video";
import LucidePhone from "~icons/lucide/phone";
import LucideEllipsis from "~icons/lucide/ellipsis";

const props = defineProps({
	meeting: { type: Object, required: true },
	past: { type: Boolean, default: false },
});
const emit = defineEmits(["edit", "changed"]);
const chat = useChat();
const calls = useCall();
const router = useRouter();

const start = computed(() => fromSite(props.meeting.starts_at));
const end = computed(() => fromSite(props.meeting.ends_at));
const durationLabel = computed(() => {
	const m = props.meeting.duration;
	return m < 60 ? `${m} min` : formatHours(m * 60);
});
const minutesAway = computed(() => (start.value.valueOf() - now.value) / 60000);
const startsSoon = computed(
	() =>
		props.meeting.status === "Scheduled" &&
		minutesAway.value <= 30 &&
		end.value.valueOf() > now.value
);
const startsIn = computed(() =>
	minutesAway.value <= 0 ? "Happening now" : `In ${Math.ceil(minutesAway.value)} min`
);
// from 10 minutes before until it ends (or while the call is still going)
const canJoin = computed(
	() =>
		props.meeting.status === "Scheduled" &&
		(props.meeting.live || (minutesAway.value <= 10 && end.value.valueOf() > now.value))
);

const place = computed(() => {
	const m = props.meeting;
	if (m.channel_type === "Direct") return "Direct chat";
	if (m.channel_type === "Group") return m.channel_name || "Group chat";
	return `#${m.channel_name}`;
});

const MARKS = {
	Accepted: { mark: "✓", markClass: "bg-green-600", label: "Going" },
	Declined: { mark: "✕", markClass: "bg-red-600", label: "Can't go" },
	Pending: { mark: "", markClass: "", label: "No answer yet" },
};
const people = computed(() => [
	{ user: props.meeting.host, response: "Accepted", ...MARKS.Accepted, label: "Host" },
	...props.meeting.invitees.map((i) => ({ ...i, ...MARKS[i.response] })),
]);
const answerSummary = computed(() => {
	const count = (r) => props.meeting.invitees.filter((i) => i.response === r).length;
	const parts = [`${count("Accepted") + 1} going`];
	if (count("Declined")) parts.push(`${count("Declined")} can't`);
	if (count("Pending")) parts.push(`${count("Pending")} no answer`);
	return parts.join(" · ");
});
const callLength = computed(() => {
	const c = props.meeting.call;
	if (!c?.ended_at) return "—";
	const seconds = (fromSite(c.ended_at).valueOf() - fromSite(c.started_at).valueOf()) / 1000;
	return formatHours(Math.max(60, seconds));
});

const menu = computed(() => {
	const m = props.meeting;
	const items = [
		{
			label: "Open chat",
			onClick: () => router.push({ name: "Conversation", params: { channel: m.channel } }),
		},
	];
	if (!props.past && m.status === "Scheduled") {
		items.push({
			label: "Add to Google Calendar",
			onClick: () => window.open(googleCalendarLink(m), "_blank", "noopener"),
		});
		if (m.is_host) {
			items.push({ label: "Edit", onClick: () => emit("edit", m) });
			items.push({ label: "Cancel meeting", onClick: cancel });
		}
	}
	return items;
});

function join() {
	calls.start(props.meeting.channel, props.meeting.call_type);
}

async function respond(response) {
	try {
		await call("aeraspace.api.meeting.respond", { name: props.meeting.name, response });
		emit("changed");
	} catch (error) {
		showError(error);
	}
}

async function cancel() {
	if (!window.confirm(`Cancel "${props.meeting.title}"? Everyone invited will be told.`)) return;
	try {
		await call("aeraspace.api.meeting.cancel", { name: props.meeting.name });
		toast.create({ message: "Meeting cancelled", type: "success" });
		emit("changed");
	} catch (error) {
		showError(error);
	}
}
</script>
