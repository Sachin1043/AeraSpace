import "./index.css";
import "./theme";

import { createApp } from "vue";
import { createPinia } from "pinia";
import { FrappeUI, setConfig, frappeRequest } from "frappe-ui";

import App from "./App.vue";
import router from "./router";
import { initRealtime } from "./socket";

setConfig("resourceFetcher", frappeRequest);

const app = createApp(App);
// socket.js owns the realtime connection (the plugin's default assumes port 9000)
app.use(FrappeUI, { socketio: false });
app.use(createPinia());
app.use(router);

function mount() {
	// server timestamps are in the site's timezone; dayjsLocal converts them for display
	setConfig("systemTimezone", window.system_timezone);
	// guests only see the login / forgot-password pages: no realtime connection
	if (window.session_user && window.session_user !== "Guest") {
		app.config.globalProperties.$socket = initRealtime();
	}
	app.mount("#app");
}

if (import.meta.env.DEV) {
	// In dev, Vite serves index.html without Jinja, so fetch the boot data Frappe would inject
	frappeRequest({ url: "/api/method/aeraspace.www.aeraspace.get_context_for_dev" }).then(
		(boot) => {
			Object.assign(window, boot);
			mount();
		}
	);
} else {
	mount();
}
