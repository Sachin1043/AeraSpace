<template>
	<div class="mx-auto max-w-4xl px-6 py-8">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">Meetings</h1>
				<p class="text-base text-ink-gray-6">Plan audio and video calls with your team.</p>
			</div>
			<div class="flex items-center gap-2">
				<div class="flex rounded-md bg-surface-gray-2 p-0.5">
					<button
						v-for="t in ['Upcoming', 'Past']"
						:key="t"
						class="rounded px-3 py-1 text-sm"
						:class="
							tab === t
								? 'bg-surface-white text-ink-gray-9 shadow-sm'
								: 'text-ink-gray-6'
						"
						@click="tab = t"
					>
						{{ t }}
					</button>
				</div>
				<Button variant="solid" @click="openSchedule()">
					<template #prefix><LucidePlus class="size-4" /></template>
					Schedule meeting
				</Button>
			</div>
		</div>

		<div v-if="list.loading && !list.data" class="flex justify-center py-12">
			<LoadingIndicator class="size-5" />
		</div>
		<div
			v-else-if="!list.data?.length"
			class="mt-6 rounded-lg border border-dashed py-12 text-center text-base text-ink-gray-5"
		>
			{{
				tab === "Upcoming"
					? "No meetings planned. Schedule one and everyone invited gets a reminder."
					: "No meetings in the last 30 days."
			}}
		</div>
		<div v-else class="mt-4">
			<section v-for="group in groups" :key="group.label" class="mt-4">
				<h2 class="mb-2 text-sm font-semibold text-ink-gray-7">{{ group.label }}</h2>
				<div class="space-y-2">
					<MeetingCard
						v-for="m in group.items"
						:key="m.name"
						:meeting="m"
						:past="tab === 'Past'"
						@edit="openSchedule"
						@changed="reload"
					/>
				</div>
			</section>
		</div>

		<ScheduleMeetingDialog
			v-model="showSchedule"
			:meeting="editing"
			:defaults="defaults"
			@saved="reload"
		/>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { Button, LoadingIndicator, createResource, dayjs } from "frappe-ui";
import { useMeetings } from "@/stores/meetings";
import { fromSite } from "@/utils/siteTime";
import MeetingCard from "@/components/MeetingCard.vue";
import ScheduleMeetingDialog from "@/components/ScheduleMeetingDialog.vue";
import LucidePlus from "~icons/lucide/plus";

const route = useRoute();
const router = useRouter();
const meetings = useMeetings();
const tab = ref("Upcoming");
const showSchedule = ref(false);
const editing = ref(null);
const defaults = ref({});

const list = createResource({ url: "aeraspace.api.meeting.get_meetings" });

function reload() {
	list.submit({ scope: tab.value === "Past" ? "past" : "upcoming" });
	meetings.load();
}

// "Today", "Tomorrow", "Friday, 20 Nov"
const groups = computed(() => {
	const out = [];
	for (const m of list.data || []) {
		const day = fromSite(m.starts_at);
		const label = day.isSame(dayjs(), "day")
			? "Today"
			: day.isSame(dayjs().add(1, "day"), "day")
			? "Tomorrow"
			: day.isSame(dayjs().subtract(1, "day"), "day")
			? "Yesterday"
			: day.format("dddd, D MMM");
		const group =
			out.find((g) => g.label === label) || out[out.push({ label, items: [] }) - 1];
		group.items.push(m);
	}
	return out;
});

function openSchedule(meeting = null, prefill = {}) {
	editing.value = meeting;
	defaults.value = prefill;
	showSchedule.value = true;
}

watch(tab, reload);
watch(() => meetings.version, reload);
onMounted(() => {
	reload();
	// /meetings?new=1&users=a,b or &channel=xyz (from a conversation)
	if (route.query.new) {
		openSchedule(null, {
			users: route.query.users ? String(route.query.users).split(",") : [],
			channel: route.query.channel || "",
		});
		router.replace({ query: {} });
	}
});
</script>
