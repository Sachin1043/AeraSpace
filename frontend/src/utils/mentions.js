// Mentions are stored as <@user@example.com> (and <!channel> for everyone) so renames never break them;
// the composer shows readable "@Full Name" text and converts on send.

const TOKEN = /<@([^>\s]+)>|<!channel>/g;

function escapeRegExp(text) {
	return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function encodeMentions(text, people) {
	let result = text.replace(/(^|\s)@channel\b/g, "$1<!channel>");
	// longest names first so "@Deva Raj" wins over "@Deva"
	const named = [...people]
		.filter((p) => p.full_name)
		.sort((a, b) => b.full_name.length - a.full_name.length);
	for (const p of named) {
		const pattern = new RegExp(`(^|[\\s(])@${escapeRegExp(p.full_name)}(?![\\w])`, "g");
		result = result.replace(pattern, `$1<@${p.user}>`);
	}
	return result;
}

export function decodeMentions(text, person) {
	return (text || "").replace(TOKEN, (match, user) =>
		user ? `@${person(user).full_name}` : "@channel"
	);
}

// Swap tokens for placeholders before markdown, then for chips after sanitising.
export function extractMentions(text) {
	const found = [];
	const replaced = (text || "").replace(TOKEN, (match, user) => {
		found.push(user || "@channel");
		return `MENTIONTOKEN${found.length - 1}X`;
	});
	return { text: replaced, found };
}

export function mentionsMe(text, user) {
	return (text || "").includes(`<@${user}>`) || (text || "").includes("<!channel>");
}
