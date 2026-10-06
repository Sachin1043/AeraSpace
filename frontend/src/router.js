import { createRouter, createWebHistory } from "vue-router";
import { session } from "@/session";

const routes = [
	{
		path: "/",
		name: "Home",
		component: () => import("@/pages/Home.vue"),
	},
	{
		path: "/people",
		name: "People",
		component: () => import("@/pages/People.vue"),
	},
	{
		path: "/channels",
		name: "Channels",
		component: () => import("@/pages/Channels.vue"),
	},
	{
		path: "/saved",
		name: "Saved",
		component: () => import("@/pages/Saved.vue"),
	},
	{
		path: "/c/:channel",
		name: "Conversation",
		component: () => import("@/pages/Conversation.vue"),
		props: true,
	},
	{
		path: "/projects",
		name: "Projects",
		component: () => import("@/pages/Projects.vue"),
	},
	{
		path: "/projects/:project",
		name: "Project",
		component: () => import("@/pages/Project.vue"),
		props: true,
	},
	{
		path: "/tasks",
		name: "Tasks",
		component: () => import("@/pages/Tasks.vue"),
	},
	{
		path: "/eod",
		name: "EOD",
		component: () => import("@/pages/Eod.vue"),
	},
	{
		path: "/timesheets",
		name: "Timesheets",
		component: () => import("@/pages/Timesheets.vue"),
	},
	{
		path: "/search",
		name: "Search",
		component: () => import("@/pages/Search.vue"),
	},
	{
		path: "/activity",
		name: "Activity",
		component: () => import("@/pages/Activity.vue"),
	},
	{
		path: "/admin/users",
		name: "AdminUsers",
		component: () => import("@/pages/AdminUsers.vue"),
		meta: { admin: true },
	},
	{
		path: "/login",
		name: "Login",
		component: () => import("@/pages/Login.vue"),
		meta: { public: true },
	},
	{
		path: "/forgot-password",
		name: "ForgotPassword",
		component: () => import("@/pages/ForgotPassword.vue"),
		meta: { public: true },
	},
	{
		path: "/:pathMatch(.*)*",
		redirect: "/",
	},
];

const router = createRouter({
	history: createWebHistory("/aeraspace"),
	routes,
});

router.beforeEach((to) => {
	if (to.meta.public) {
		// already signed in: the login page has nothing to offer
		return session.isLoggedIn && to.name === "Login"
			? { path: to.query.redirect || "/" }
			: true;
	}
	if (!session.isLoggedIn)
		return { name: "Login", query: to.fullPath !== "/" ? { redirect: to.fullPath } : {} };
	if (to.meta.admin && !session.isAdmin) return { path: "/" };
	return true;
});

export default router;
