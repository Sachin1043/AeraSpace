app_name = "aeraspace"
app_title = "AeraSpace"
app_publisher = "Aerele"
app_description = "Aerele internal workspace for chat, channels, projects and tasks"
app_email = "bhavansathru.it@gmail.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "aeraspace",
# 		"logo": "/assets/aeraspace/logo.png",
# 		"title": "AeraSpace",
# 		"route": "/aeraspace",
# 		"has_permission": "aeraspace.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/aeraspace/css/aeraspace.css"
# app_include_js = "/assets/aeraspace/js/aeraspace.js"

# include js, css files in header of web template
# web_include_css = "/assets/aeraspace/css/aeraspace.css"
# web_include_js = "/assets/aeraspace/js/aeraspace.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "aeraspace/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "aeraspace/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# automatically load and sync documents of this doctype from downstream apps
# importable_doctypes = [doctype_1]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "aeraspace.utils.jinja_methods",
# 	"filters": "aeraspace.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "aeraspace.install.before_install"
# after_install = "aeraspace.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "aeraspace.uninstall.before_uninstall"
# after_uninstall = "aeraspace.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "aeraspace.utils.before_app_install"
# after_app_install = "aeraspace.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "aeraspace.utils.before_app_uninstall"
# after_app_uninstall = "aeraspace.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "aeraspace.build.after_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "aeraspace.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["aeraspace.search.awesomebar_results"]

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"aeraspace.tasks.all"
# 	],
# 	"daily": [
# 		"aeraspace.tasks.daily"
# 	],
# 	"hourly": [
# 		"aeraspace.tasks.hourly"
# 	],
# 	"weekly": [
# 		"aeraspace.tasks.weekly"
# 	],
# 	"monthly": [
# 		"aeraspace.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "aeraspace.install.before_tests"

# Extend DocType Class
# ------------------------------
#
# Specify custom mixins to extend the standard doctype controller.
# extend_doctype_class = {
# 	"Task": "aeraspace.custom.task.CustomTaskMixin"
# }

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "aeraspace.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "aeraspace.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["aeraspace.utils.before_request"]
# after_request = ["aeraspace.utils.after_request"]

# Job Events
# ----------
# before_job = ["aeraspace.utils.before_job"]
# after_job = ["aeraspace.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"aeraspace.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []


# Single-page app
# ---------------

website_route_rules = [
	{"from_route": "/aeraspace/<path:app_path>", "to_route": "aeraspace"},
]

doc_events = {
	"User": {
		"on_update": "aeraspace.api.directory.create_profile_for_user",
	},
	"Employee Checkin": {
		"validate": "aeraspace.hr.protect_checkin",
		"on_trash": "aeraspace.hr.protect_checkin",
	},
}

after_install = "aeraspace.install.after_install"
after_migrate = "aeraspace.install.after_migrate"

has_permission = {
	"AS Channel": "aeraspace.permissions.channel_has_permission",
}

permission_query_conditions = {
	"AS Channel": "aeraspace.permissions.channel_query_conditions",
}

scheduler_events = {
	"cron": {
		"*/15 * * * *": ["aeraspace.tasks.eod_reminders"],
	},
}
