import { createRouter, createWebHistory } from "vue-router";

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
		path: "/:pathMatch(.*)*",
		redirect: "/",
	},
];

export default createRouter({
	history: createWebHistory("/aeraspace"),
	routes,
});
