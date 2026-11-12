<template>
	<div class="rounded-lg border p-3">
		<div class="flex items-start gap-3">
			<UserAvatar v-if="showPerson" :user="row.user" size="lg" :show-presence="false" />
			<div
				v-else
				class="flex size-8 shrink-0 items-center justify-center rounded-full bg-surface-gray-2"
			>
				<component :is="icon" class="size-4 text-ink-gray-7" />
			</div>
			<div class="min-w-0 flex-1">
				<div class="flex flex-wrap items-center gap-x-2 gap-y-1">
					<span v-if="showPerson" class="text-base font-semibold text-ink-gray-9">
						{{ row.full_name }}
					</span>
					<span
						class="text-base"
						:class="showPerson ? 'text-ink-gray-7' : 'font-semibold text-ink-gray-9'"
					>
						{{ row.title }}
					</span>
					<span
						class="rounded-full px-2 py-0.5 text-xs font-medium"
						:class="statusClass"
					>
						{{ row.status }}
					</span>
				</div>
				<div class="mt-0.5 text-sm text-ink-gray-6">
					{{ when }} · {{ row.days }} {{ row.days === 1 ? "day" : "days" }}
					<template v-if="row.half_day">
						· half day on {{ dayjs(row.half_day_date).format("D MMM") }}
					</template>
				</div>
				<p v-if="row.reason" class="mt-1.5 whitespace-pre-line text-base text-ink-gray-8">
					{{ row.reason }}
				</p>
				<p v-if="row.note" class="mt-1.5 text-sm text-ink-gray-6">
					<b class="font-medium text-ink-gray-7">{{ row.approver_name }}:</b>
					{{ row.note }}
				</p>
				<p
					v-else-if="!showPerson && row.status === 'Pending'"
					class="mt-1.5 text-sm text-ink-gray-5"
				>
					Waiting for {{ row.approver_name }}
				</p>
			</div>
			<div class="flex shrink-0 items-center gap-2">
				<template v-if="row.can_decide">
					<Button theme="red" :loading="busy === 'reject'" @click="$emit('reject', row)">
						Reject
					</Button>
					<Button
						variant="solid"
						theme="green"
						:loading="busy === 'approve'"
						@click="$emit('approve', row)"
					>
						Approve
					</Button>
				</template>
				<Button
					v-else-if="row.can_cancel"
					:loading="busy === 'cancel'"
					@click="$emit('cancel', row)"
				>
					Cancel
				</Button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { Button, dayjs } from "frappe-ui";
import { REQUEST_STATUS_STYLES } from "@/stores/requests";
import UserAvatar from "./UserAvatar.vue";
import LucidePlane from "~icons/lucide/plane";
import LucideHouse from "~icons/lucide/house";
import LucideClockAlert from "~icons/lucide/clock-alert";

const props = defineProps({
	row: { type: Object, required: true },
	showPerson: { type: Boolean, default: false },
	busy: { type: String, default: null },
});
defineEmits(["approve", "reject", "cancel"]);

const icon = computed(
	() => ({ leave: LucidePlane, wfh: LucideHouse, correction: LucideClockAlert }[props.row.kind])
);
const statusClass = computed(() => REQUEST_STATUS_STYLES[props.row.status]);
const when = computed(() => {
	const start = dayjs(props.row.from_date);
	const end = dayjs(props.row.to_date);
	if (start.isSame(end, "day")) return start.format("ddd, D MMM YYYY");
	return `${start.format("D MMM")} – ${end.format("D MMM YYYY")}`;
});
</script>
