<template>
	<AuthCard title="Sign in to AeraSpace" subtitle="One Space. Everyone Connected.">
		<form class="space-y-4" @submit.prevent="login">
			<!-- text, not type=email: Frappe also accepts usernames such as "Administrator" -->
			<FormControl
				v-model="email"
				label="Email or username"
				type="text"
				inputmode="email"
				autocapitalize="off"
				autocomplete="username"
				placeholder="you@aerele.in"
			/>
			<div>
				<FormControl
					v-model="password"
					label="Password"
					:type="showPassword ? 'text' : 'password'"
					autocomplete="current-password"
				/>
				<div class="mt-1.5 flex items-center justify-between text-xs">
					<label class="flex items-center gap-1.5 text-ink-gray-6">
						<input v-model="showPassword" type="checkbox" class="rounded" /> Show
						password
					</label>
					<router-link
						:to="{ name: 'ForgotPassword', query: { email } }"
						class="text-ink-blue-3 hover:underline"
					>
						Forgot password?
					</router-link>
				</div>
			</div>
			<div v-if="error" class="rounded-md bg-surface-red-2 px-3 py-2 text-sm text-ink-red-4">
				{{ error }}
			</div>
			<Button
				variant="solid"
				class="w-full"
				type="submit"
				:loading="loading"
				:disabled="!email || !password"
			>
				Sign in
			</Button>
		</form>
		<template #footer>Don't have an account? Ask your admin to add you.</template>
	</AuthCard>
</template>

<script setup>
import { ref } from "vue";
import { useRoute } from "vue-router";
import { Button, FormControl, call } from "frappe-ui";
import AuthCard from "@/components/AuthCard.vue";

const route = useRoute();
const email = ref(route.query.email || "");
const password = ref("");
const showPassword = ref(false);
const loading = ref(false);
const error = ref("");

async function login() {
	loading.value = true;
	error.value = "";
	try {
		await call("login", { usr: email.value.trim(), pwd: password.value });
		// full reload so the page picks up the new session (boot data, CSRF token, realtime)
		const target = String(route.query.redirect || "/");
		window.location.href = `/aeraspace${target.startsWith("/") ? target : "/"}`;
	} catch (e) {
		error.value = e?.messages?.[0] || "Invalid email or password";
		loading.value = false;
	}
}
</script>
