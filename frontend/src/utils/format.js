import { Marked } from "marked";
import DOMPurify from "dompurify";
import { extractMentions } from "./mentions";

// Chat-flavoured markdown: **bold**, _italic_, `code`, ``` blocks ```, lists, quotes and links.
// Headings are rendered as plain paragraphs so a "# note" doesn't shout.
const marked = new Marked({
	gfm: true,
	breaks: true,
	renderer: {
		heading({ tokens }) {
			return `<p><strong>${this.parser.parseInline(tokens)}</strong></p>`;
		},
	},
});

const ALLOWED_TAGS = [
	"p",
	"br",
	"strong",
	"b",
	"em",
	"i",
	"del",
	"s",
	"code",
	"pre",
	"a",
	"ul",
	"ol",
	"li",
	"blockquote",
	"hr",
];

DOMPurify.addHook("afterSanitizeAttributes", (node) => {
	if (node.tagName === "A") {
		node.setAttribute("target", "_blank");
		node.setAttribute("rel", "noopener noreferrer");
	}
});

function escapeHtml(text) {
	return text.replace(
		/[&<>"']/g,
		(c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
	);
}

// person(user) -> { full_name }, me -> current user (their mentions are highlighted stronger)
export function renderMarkdown(text, { person, me } = {}) {
	if (!text) return "";
	const { text: withPlaceholders, found } = extractMentions(text);
	const html = DOMPurify.sanitize(marked.parse(withPlaceholders), {
		ALLOWED_TAGS,
		ALLOWED_ATTR: ["href", "target", "rel"],
	});
	return html.replace(/MENTIONTOKEN(\d+)X/g, (match, index) => {
		const user = found[Number(index)];
		if (user === "@channel") return '<span class="mention mention-me">@channel</span>';
		const name = person ? person(user).full_name : user;
		return `<span class="mention${user === me ? " mention-me" : ""}" data-user="${escapeHtml(
			user
		)}">@${escapeHtml(name)}</span>`;
	});
}

// One-line previews (quotes, sidebar, search…): readable mentions, no markdown symbols
export function plainText(text, person) {
	return (text || "")
		.replace(/<@([^>\s]+)>/g, (m, user) => `@${person ? person(user).full_name : user}`)
		.replace(/<!channel>/g, "@channel")
		.replace(/```[a-z]*\n?/gi, "")
		.replace(/`([^`]*)`/g, "$1")
		.replace(/(\*\*|__)(.+?)\1/g, "$2")
		.replace(/(^|\s)[*_](\S[^*_]*?)[*_](?=\s|$|[.,!?])/g, "$1$2")
		.replace(/~~(.+?)~~/g, "$1")
		.replace(/^\s*(#{1,6}|>)\s+/gm, "")
		.replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
		.replace(/\s+/g, " ")
		.trim();
}

const IMAGE_EXTENSIONS = ["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "avif"];

export function fileExtension(name = "") {
	return name.includes(".") ? name.split(".").pop().toLowerCase() : "";
}

export function isImage(file) {
	return IMAGE_EXTENSIONS.includes(fileExtension(file?.file_name));
}

export function formatSize(bytes) {
	if (!bytes && bytes !== 0) return "";
	const units = ["B", "KB", "MB", "GB"];
	let size = bytes;
	let unit = 0;
	while (size >= 1024 && unit < units.length - 1) {
		size /= 1024;
		unit++;
	}
	return `${size.toFixed(unit === 0 ? 0 : 1)} ${units[unit]}`;
}
