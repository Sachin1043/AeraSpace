<template>
	<div class="mx-auto max-w-6xl px-6 py-8">
		<div class="flex flex-wrap items-center justify-between gap-3">
			<div>
				<h1 class="text-xl font-semibold text-ink-gray-9">Users</h1>
				<p class="text-base text-ink-gray-6">
					Everyone with an AeraSpace account. Only admins see this page.
				</p>
			</div>
			<Button variant="solid" @click="openForm(null)">
				<template #prefix><LucideUserPlus class="size-4" /></template>
				New user
			</Button>
		</div>

		<div class="mt-5 flex gap-1 border-b">
			<button
				v-for="t in tabs"
				:key="t.key"
				class="-mb-px flex items-center gap-1.5 border-b-2 px-3 py-1.5 text-sm"
				:class="
					tab === t.key
						? 'border-ink-gray-9 font-medium text-ink-gray-9'
						: 'border-transparent text-ink-gray-6 hover:text-ink-gray-8'
				"
				@click="setTab(t.key)"
			>
				{{ t.label }}
				<span
					v-if="t.count"
					class="rounded-full bg-red-500 px-1.5 text-2xs font-medium leading-4 text-white"
					>{{ t.count }}</span
				>
			</button>
		</div>

		<!-- users -->
		<template v-if="tab === 'users'">
			<div class="mt-4 flex flex-wrap items-center gap-2">
				<TextInput v-model="search" class="w-72" placeholder="Search name, email, team…">
					<template #prefix><LucideSearch class="size-4 text-ink-gray-5" /></template>
				</TextInput>
				<div class="flex rounded-md bg-surface-gray-2 p-0.5">
					<button
						v-for="s in ['all', 'active', 'disabled']"
						:key="s"
						class="rounded px-2.5 py-1 text-sm capitalize"
						:class="
							status === s
								? 'bg-surface-white text-ink-gray-9 shadow-sm'
								: 'text-ink-gray-6'
						"
						@click="status = s"
					>
						{{ s }}
					</button>
				</div>
				<span class="ml-auto text-sm text-ink-gray-5"
					>{{ visible.length }} of {{ users.data?.length || 0 }}</span
				>
			</div>

			<div v-if="users.loading && !users.data" class="flex justify-center py-10">
				<LoadingIndicator class="size-5" />
			</div>
			<div v-else class="mt-3 overflow-x-auto rounded-lg border">
				<table class="w-full text-left text-sm">
					<thead class="bg-surface-gray-1 text-xs uppercase text-ink-gray-5">
						<tr>
							<th class="px-3 py-2 font-medium">Person</th>
							<th class="px-3 py-2 font-medium">Role & team</th>
							<th class="px-3 py-2 font-medium">Reporting to</th>
							<th class="px-3 py-2 font-medium">Last login</th>
							<th class="px-3 py-2 font-medium">Status</th>
							<th class="px-3 py-2" />
						</tr>
					</thead>
					<tbody class="divide-y">
						<tr
							v-for="u in visible"
							:key="u.user"
							:class="{ 'opacity-60': !u.enabled }"
						>
							<td class="px-3 py-2">
								<div class="flex items-center gap-3">
									<Avatar :label="u.full_name" :image="u.user_image" size="lg" />
									<div class="min-w-0">
										<div class="flex items-center gap-1.5">
											<span class="truncate text-base text-ink-gray-9">{{
												u.full_name
											}}</span>
											<span
												v-if="u.user === session.user"
												class="text-xs text-ink-gray-5"
												>(you)</span
											>
											<span
												v-if="u.is_admin"
												class="rounded bg-surface-violet-1 px-1.5 text-2xs font-medium text-ink-violet-1"
												>Admin</span
											>
										</div>
										<div class="truncate text-xs text-ink-gray-5">
											{{ u.email || u.user }}
										</div>
									</div>
								</div>
							</td>
							<td class="px-3 py-2 text-ink-gray-7">
								<div>{{ u.designation || "—" }}</div>
								<div class="text-xs text-ink-gray-5">
									{{ [u.department, u.team].filter(Boolean).join(" · ") }}
								</div>
							</td>
							<td class="px-3 py-2 text-ink-gray-7">
								{{ u.manager ? nameOf(u.manager) : "—" }}
							</td>
							<td class="px-3 py-2 text-ink-gray-6">
								{{ u.last_login ? dayjsLocal(u.last_login).fromNow() : "Never" }}
							</td>
							<td class="px-3 py-2">
								<span
									class="rounded px-1.5 py-0.5 text-xs font-medium"
									:class="
										u.enabled
											? 'bg-surface-green-2 text-ink-green-3'
											: 'bg-surface-gray-2 text-ink-gray-6'
									"
								>
									{{ u.enabled ? "Active" : "Disabled" }}
								</span>
								<span
									v-if="!u.is_aeraspace_user"
									class="ml-1 text-xs text-ink-amber-3"
									title="Missing the AeraSpace User role"
									>⚠</span
								>
							</td>
							<td class="px-3 py-2 text-right">
								<Dropdown :options="rowActions(u)" placement="right">
									<Button variant="ghost" size="sm"
										><LucideEllipsis class="size-4"
									/></Button>
								</Dropdown>
							</td>
						</tr>
					</tbody>
				</table>
				<div
					v-if="!visible.length"
					class="px-4 py-10 text-center text-base text-ink-gray-5"
				>
					No users match.
				</div>
			</div>
		</template>

		<!-- password requests -->
		<template v-else>
			<div class="mt-4 flex items-center gap-2">
				<div class="flex rounded-md bg-surface-gray-2 p-0.5">
					<button
						v-for="s in ['Pending', 'all']"
						:key="s"
						class="rounded px-2.5 py-1 text-sm"
						:class="
							requestFilter === s
								? 'bg-surface-white text-ink-gray-9 shadow-sm'
								: 'text-ink-gray-6'
						"
						@click="requestFilter = s"
					>
						{{ s === "all" ? "History" : "Waiting" }}
					</button>
				</div>
				<span class="text-sm text-ink-gray-5"
					>Approve only if you're sure it's really them (e.g. they asked you in
					person).</span
				>
			</div>
			<div v-if="requests.loading && !requests.data" class="flex justify-center py-10">
				<LoadingIndicator class="size-5" />
			</div>
			<div
				v-else-if="!requests.data?.length"
				class="mt-3 rounded-lg border px-4 py-10 text-center text-base text-ink-gray-5"
			>
				{{
					requestFilter === "Pending"
						? "No one is waiting for a password reset."
						: "No requests yet."
				}}
			</div>
			<div v-else class="mt-3 divide-y rounded-lg border">
				<div
					v-for="r in requests.data"
					:key="r.name"
					class="flex flex-wrap items-center gap-3 px-4 py-3"
				>
					<UserAvatar :user="r.user" size="lg" :show-presence="false" />
					<div class="min-w-0 flex-1">
						<div class="text-base text-ink-gray-9">
							{{ r.full_name }}
							<span class="text-sm text-ink-gray-5">{{ r.user }}</span>
						</div>
						<div class="text-xs text-ink-gray-5">
							Asked {{ dayjsLocal(r.creation).fromNow()
							}}<span v-if="r.ip_address"> · from {{ r.ip_address }}</span>
							<span v-if="r.reviewed_by">
								· {{ r.status.toLowerCase() }} by {{ nameOf(r.reviewed_by) }}</span
							>
						</div>
					</div>
					<template v-if="r.status === 'Pending'">
						<Button :loading="acting === r.name" @click="decide(r, 'reject')"
							>Reject</Button
						>
						<Button
							variant="solid"
							:loading="acting === r.name"
							@click="decide(r, 'approve')"
							>Approve</Button
						>
					</template>
					<span
						v-else
						class="rounded px-1.5 py-0.5 text-xs font-medium"
						:class="requestStyles[r.status]"
						>{{ r.status }}</span
					>
				</div>
			</div>
		</template>

		<UserFormDialog
			v-model="showForm"
			:user="editing"
			:people="users.data || []"
			@saved="onSaved"
		/>

		<!-- one-time credentials -->
		<Dialog v-model="showCredentials" :options="{ title: credentials.title, size: 'md' }">
			<template #body-content>
				<p class="text-base text-ink-gray-7">
					Share these with {{ credentials.email }} privately. The password won't be shown
					again.
				</p>
				<div
					class="mt-3 space-y-2 rounded-lg border bg-surface-gray-1 p-3 font-mono text-sm"
				>
					<div>
						Sign in: <b>{{ loginUrl }}</b>
					</div>
					<div>
						Email: <b>{{ credentials.email }}</b>
					</div>
					<div v-if="credentials.password">
						Password: <b>{{ credentials.password }}</b>
					</div>
				</div>
			</template>
			<template #actions>
				<Button variant="solid" class="w-full" @click="copyCredentials">
					<template #prefix><LucideCopy class="size-4" /></template>
					Copy
				</Button>
			</template>
		</Dialog>
	</div>
</template>

<script setup>
import { computed, onBeforeUnmount, reactive, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
	Avatar,
	Button,
	Dialog,
	Dropdown,
	LoadingIndicator,
	TextInput,
	call,
	createResource,
	dayjsLocal,
	toast,
} from "frappe-ui";
import { showError, useChat } from "@/stores/chat";
import { session } from "@/session";
import UserAvatar from "@/components/UserAvatar.vue";
import UserFormDialog from "@/components/UserFormDialog.vue";
import LucideUserPlus from "~icons/lucide/user-plus";
import LucideSearch from "~icons/lucide/search";
import LucideEllipsis from "~icons/lucide/ellipsis";
import LucideCopy from "~icons/lucide/copy";

const chat = useChat();
const route = useRoute();
const router = useRouter();

const tab = ref(route.query.tab === "requests" ? "requests" : "users");
const search = ref("");
const status = ref("all");
const showForm = ref(false);
const editing = ref(null);
const requestFilter = ref("Pending");
const acting = ref(null);
const showCredentials = ref(false);
const credentials = reactive({ title: "", email: "", password: "" });
const loginUrl = `${window.location.origin}/aeraspace/login`;

const users = createResource({ url: "aeraspace.api.admin_users.list_users", auto: true });
const requests = createResource({ url: "aeraspace.api.admin_users.list_reset_requests" });

const tabs = computed(() => [
	{ key: "users", label: "Users" },
	{ key: "requests", label: "Password requests", count: chat.pendingResets },
]);
const requestStyles = {
	Approved: "bg-surface-blue-1 text-ink-blue-3",
	Completed: "bg-surface-green-2 text-ink-green-3",
	Rejected: "bg-surface-red-2 text-ink-red-4",
	Expired: "bg-surface-gray-2 text-ink-gray-6",
};

const visible = computed(() => {
	const term = search.value.trim().toLowerCase();
	return (users.data || []).filter((u) => {
		if (status.value === "active" && !u.enabled) return false;
		if (status.value === "disabled" && u.enabled) return false;
		return (
			!term ||
			[u.full_name, u.user, u.designation, u.department, u.team].some((v) =>
				v?.toLowerCase().includes(term)
			)
		);
	});
});

function nameOf(user) {
	return (
		(users.data || []).find((u) => u.user === user)?.full_name || chat.person(user).full_name
	);
}

function setTab(key) {
	tab.value = key;
	router.replace({ query: key === "requests" ? { tab: "requests" } : {} });
}

function openForm(user) {
	editing.value = user;
	showForm.value = true;
}

function onSaved(created) {
	users.reload();
	if (created) {
		Object.assign(credentials, {
			title: "User created",
			email: created.email,
			password: created.password,
		});
		showCredentials.value = true;
	}
}

function rowActions(u) {
	const self = u.user === session.user || u.user === "Administrator";
	return [
		{ label: "Edit details", icon: "edit-2", onClick: () => openForm(u) },
		{ label: "Reset password", icon: "key", onClick: () => resetPassword(u) },
		!self && {
			label: u.enabled ? "Disable" : "Enable",
			icon: u.enabled ? "user-x" : "user-check",
			onClick: () => toggleEnabled(u),
		},
	].filter(Boolean);
}

async function resetPassword(u) {
	if (!window.confirm(`Reset ${u.full_name}'s password? They'll be signed out everywhere.`))
		return;
	try {
		const result = await call("aeraspace.api.admin_users.set_password", { user: u.user });
		Object.assign(credentials, {
			title: "New password",
			email: u.email || u.user,
			password: result.password,
		});
		showCredentials.value = true;
	} catch (error) {
		showError(error);
	}
}

async function toggleEnabled(u) {
	if (
		u.enabled &&
		!window.confirm(
			`Disable ${u.full_name}? They'll be signed out and can't sign in until enabled again.`
		)
	)
		return;
	try {
		await call("aeraspace.api.admin_users.set_enabled", {
			user: u.user,
			enabled: u.enabled ? 0 : 1,
		});
		users.reload();
	} catch (error) {
		showError(error);
	}
}

async function decide(request, action) {
	if (
		action === "approve" &&
		!window.confirm(
			`Approve the password reset for ${request.full_name}? They'll be able to set a new password for the next 24 hours.`
		)
	)
		return;
	acting.value = request.name;
	try {
		await call(`aeraspace.api.admin_users.${action}_reset_request`, { name: request.name });
		toast.create({
			message:
				action === "approve"
					? "Approved — they can now set a new password"
					: "Request rejected",
			type: "success",
		});
		requests.reload();
		chat.loadPendingResets();
	} catch (error) {
		showError(error);
	} finally {
		acting.value = null;
	}
}

function copyCredentials() {
	const lines = [`Sign in: ${loginUrl}`, `Email: ${credentials.email}`];
	if (credentials.password) lines.push(`Password: ${credentials.password}`);
	navigator.clipboard?.writeText(lines.join("\n"));
	toast.create({ message: "Copied", type: "success" });
}

watch(
	[tab, requestFilter],
	([t]) => t === "requests" && requests.submit({ status: requestFilter.value }),
	{ immediate: true }
);
// new requests arrive live
watch(
	() => chat.pendingResets,
	() => tab.value === "requests" && requests.reload()
);
onBeforeUnmount(() => (showCredentials.value = false));
</script>
