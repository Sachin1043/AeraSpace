<template>
	<Popover placement="bottom-end" @update:show="(v) => !v && (choosing = false)">
		<template #target="{ togglePopover }">
			<button
				class="flex items-center rounded-full p-0.5 hover:bg-surface-gray-3"
				:title="`${session.fullName} — ${chat.statusLabel(session.user)}`"
				aria-label="Your status and settings"
				@click="togglePopover"
			>
				<UserAvatar :user="session.user" size="lg" />
			</button>
		</template>

		<template #body-main="{ close }">
			<div class="w-80">
				<!-- who -->
				<div class="flex flex-col items-center gap-1 border-b px-4 pb-4 pt-5 text-center">
					<UserAvatar :user="session.user" size="3xl" />
					<div class="mt-1 text-base font-semibold text-ink-gray-9">
						{{ session.fullName }}
					</div>
					<div class="text-sm text-ink-gray-5">{{ me.email || session.user }}</div>

					<!-- live work clock while checked in -->
					<template v-if="attendance.enabled">
						<div
							v-if="attendance.state !== 'out'"
							class="mt-2 flex items-center gap-2 rounded-full px-3 py-1 text-sm"
							:class="
								onBreak
									? 'bg-surface-amber-2 text-ink-amber-3'
									: 'bg-surface-green-2 text-ink-green-3'
							"
							:title="`${onBreak ? 'On break' : 'Working'} since ${
								attendance.sinceTime
							}`"
						>
							<span
								class="size-2 animate-pulse rounded-full"
								:class="onBreak ? 'bg-[#f5a623]' : 'bg-[#2ecc71]'"
							/>
							<span class="text-xs">{{ onBreak ? "On break" : "Working" }}</span>
							<span class="font-mono font-semibold tabular-nums">{{
								formatClock(
									onBreak ? attendance.runningSeconds : attendance.workedSeconds
								)
							}}</span>
						</div>
						<!-- checked out: today's final worked time -->
						<div
							v-else-if="attendance.data.today.first_in"
							class="mt-2 flex items-center gap-2 rounded-full bg-surface-gray-2 px-3 py-1 text-sm text-ink-gray-6"
							:title="`Worked today · last check-out at ${attendance.time(
								attendance.data.today.last_out
							)}`"
						>
							<span class="size-2 rounded-full bg-surface-gray-5" />
							<span class="text-xs">Checked out</span>
							<span class="font-mono font-semibold tabular-nums">{{
								formatClock(attendance.workedSeconds)
							}}</span>
						</div>
						<div v-else class="mt-2 text-xs text-ink-gray-5">Checked out</div>
					</template>

					<!-- the one current status -->
					<button
						class="mt-3 flex w-full items-center gap-2 rounded-md border px-3 py-2 text-left text-base hover:bg-surface-gray-1"
						:class="{ 'border-outline-gray-4': choosing }"
						@click="choosing = !choosing"
					>
						<span v-if="current.emoji" class="w-4 text-center">{{
							current.emoji
						}}</span>
						<PresenceDot v-else :status="chat.statusOf(session.user)" size="md" />
						<span class="flex-1 truncate text-ink-gray-8">{{ current.label }}</span>
						<LucideChevronDown
							class="size-4 text-ink-gray-5 transition-transform"
							:class="{ 'rotate-180': choosing }"
						/>
					</button>
				</div>

				<!-- pick one -->
				<div v-if="choosing" class="max-h-[22rem] overflow-y-auto border-b py-1.5">
					<div
						class="px-4 pb-1 pt-1 text-2xs font-medium uppercase tracking-wide text-ink-gray-5"
					>
						Default status
					</div>
					<button
						v-for="option in DEFAULT_STATUSES"
						:key="option.value"
						class="flex w-full items-center gap-3 px-4 py-1.5 text-left hover:bg-surface-gray-2"
						@click="pick({ availability: option.value }, close)"
					>
						<PresenceDot :status="option.status" size="md" />
						<div class="min-w-0 flex-1">
							<div class="text-base text-ink-gray-8">{{ option.label }}</div>
							<div v-if="option.hint" class="truncate text-2xs text-ink-gray-5">
								{{ option.hint }}
							</div>
						</div>
						<LucideCheck
							v-if="current.key === option.value"
							class="size-4 text-ink-green-3"
						/>
					</button>

					<div
						class="px-4 pb-1 pt-3 text-2xs font-medium uppercase tracking-wide text-ink-gray-5"
					>
						Custom status
					</div>
					<button
						v-for="option in CUSTOM_STATUSES"
						:key="option.text"
						class="flex w-full items-center gap-3 px-4 py-1.5 text-left hover:bg-surface-gray-2"
						@click="
							pick(
								{
									availability: option.value,
									emoji: option.emoji,
									text: option.text,
								},
								close
							)
						"
					>
						<span class="w-4 text-center">{{ option.emoji }}</span>
						<span class="flex-1 text-base text-ink-gray-8">{{ option.text }}</span>
						<LucideCheck
							v-if="current.key === option.text"
							class="size-4 text-ink-green-3"
						/>
					</button>
					<button
						class="flex w-full items-center gap-3 px-4 py-1.5 text-left hover:bg-surface-gray-2"
						@click="
							close();
							chat.viewProfile(session.user);
						"
					>
						<LucidePencil class="size-4 text-ink-gray-5" />
						<span class="text-base text-ink-gray-7">Set a custom status…</span>
					</button>
				</div>

				<!-- settings -->
				<div class="py-1.5">
					<button
						class="menu-row"
						@click="
							close();
							chat.viewProfile(session.user);
						"
					>
						<LucideUser class="size-4" /> My profile
					</button>
					<button
						v-if="session.isAdmin"
						class="menu-row"
						@click="
							close();
							$router.push({ name: 'AdminUsers' });
						"
					>
						<LucideUsers class="size-4" />
						<span class="flex-1">Users</span>
						<span
							v-if="chat.pendingResets"
							class="rounded-full bg-red-500 px-1.5 text-2xs font-medium leading-4 text-white"
							:title="`${chat.pendingResets} password reset request(s) waiting`"
						>
							{{ chat.pendingResets }}
						</span>
					</button>
					<div class="flex items-center gap-3 px-4 py-1.5 text-base text-ink-gray-7">
						<LucideSunMoon class="size-4" />
						<span class="flex-1">Theme</span>
						<div class="flex rounded-md bg-surface-gray-2 p-0.5">
							<button
								v-for="t in themes"
								:key="t.value"
								class="rounded px-2 py-0.5 text-xs"
								:class="
									theme === t.value
										? 'bg-surface-white text-ink-gray-9 shadow-sm'
										: 'text-ink-gray-6'
								"
								@click="setTheme(t.value)"
							>
								{{ t.label }}
							</button>
						</div>
					</div>
					<button
						v-if="chat.notificationPermission === 'default'"
						class="menu-row"
						@click="chat.enableDesktopNotifications()"
					>
						<LucideBell class="size-4" /> Enable desktop notifications
					</button>
					<button class="menu-row text-ink-red-4" @click="session.logout()">
						<LucideLogOut class="size-4" /> Log out
					</button>
				</div>
			</div>
		</template>
	</Popover>
</template>

<script setup>
import { computed, ref } from "vue";
import { Popover } from "frappe-ui";
import { useChat } from "@/stores/chat";
import { session } from "@/session";
import { setTheme, theme } from "@/theme";
import { CUSTOM_STATUSES, DEFAULT_STATUSES } from "@/utils/status";
import { useAttendance } from "@/stores/attendance";
import { formatClock } from "@/utils/clock";
import UserAvatar from "./UserAvatar.vue";
import PresenceDot from "./PresenceDot.vue";
import LucideChevronDown from "~icons/lucide/chevron-down";
import LucideCheck from "~icons/lucide/check";
import LucidePencil from "~icons/lucide/pencil";
import LucideUser from "~icons/lucide/user";
import LucideUsers from "~icons/lucide/users";
import LucideSunMoon from "~icons/lucide/sun-moon";
import LucideBell from "~icons/lucide/bell";
import LucideLogOut from "~icons/lucide/log-out";

const chat = useChat();
const attendance = useAttendance();
const onBreak = computed(() => attendance.state === "break");
const choosing = ref(false);
const me = computed(() => chat.person(session.user));
const themes = [
	{ value: "light", label: "Light" },
	{ value: "dark", label: "Dark" },
	{ value: "system", label: "System" },
];

// exactly one status is current: a custom message wins, otherwise the availability
const current = computed(() => {
	if (me.value.status_text || me.value.status_emoji) {
		return {
			key: me.value.status_text,
			label: me.value.status_text || "Custom status",
			emoji: me.value.status_emoji,
		};
	}
	const option =
		DEFAULT_STATUSES.find((s) => s.value === (me.value.availability || "Auto")) ||
		DEFAULT_STATUSES[0];
	return { key: option.value, label: option.label };
});

async function pick(status, close) {
	choosing.value = false;
	close();
	await chat.setStatus(status);
}
</script>

<style scoped>
.menu-row {
	display: flex;
	width: 100%;
	align-items: center;
	gap: 0.75rem;
	padding: 0.375rem 1rem;
	text-align: left;
	font-size: 0.875rem;
	color: var(--ink-gray-7);
}
.menu-row:hover {
	background: var(--surface-gray-2);
}
</style>
