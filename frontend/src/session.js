import { frappeRequest } from "frappe-ui";

export const session = {
	get user() {
		return window.session_user;
	},
	get fullName() {
		return window.user_fullname || window.session_user;
	},
	get image() {
		return window.user_image;
	},
	async logout() {
		await frappeRequest({ url: "/api/method/logout" });
		window.location.href = "/login?redirect-to=/aeraspace";
	},
};
