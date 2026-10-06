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
	get isLoggedIn() {
		return !!window.session_user && window.session_user !== "Guest";
	},
	get isAdmin() {
		return !!window.is_admin;
	},
	async logout() {
		await frappeRequest({ url: "/api/method/logout" });
		window.location.href = "/aeraspace/login";
	},
};
