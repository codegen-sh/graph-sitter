export const auraCodeTheme = {
	name: "Aura Dark",
	type: "dark",
	colors: {
		"editor.background": "#15141b",
		"editor.foreground": "#edecee",
		"editor.selectionBackground": "#3d375e7f",
		"editor.lineHighlightBackground": "#a394f033",
		"editorCursor.foreground": "#a277ff",
	},
	tokenColors: [
		{
			scope: [
				"keyword",
				"storage",
				"support",
				"entity.name.tag",
				"variable.language",
				"keyword.control.flow",
				"keyword.operator",
			],
			settings: { foreground: "#a277ff" },
		},
		{
			scope: [
				"string",
				"markup.inserted",
				"markup.raw",
				"constant",
				"source.env",
				"variable.other.quoted",
			],
			settings: { foreground: "#61ffca" },
		},
		{
			scope: [
				"entity",
				"entity.name.function",
				"support.function",
				"entity.name.section.markdown",
			],
			settings: { foreground: "#ffca85" },
		},
		{
			scope: [
				"entity.name.type",
				"entity.name.class",
				"support.class",
				"support.type",
			],
			settings: { foreground: "#82e2ff" },
		},
		{
			scope: [
				"entity.other.attribute-name",
				"meta.object-literal.key",
				"variable.other.property",
				"meta.attribute.python",
			],
			settings: { foreground: "#f694ff" },
		},
		{
			scope: ["invalid", "markup.deleted"],
			settings: { foreground: "#ff6767" },
		},
		{
			scope: ["comment", "string.quoted.docstring.multi.python"],
			settings: { foreground: "#6d6d6d", fontStyle: "italic" },
		},
		{
			scope: ["variable", "variable.parameter", "markup.list"],
			settings: { foreground: "#edecee" },
		},
		{
			scope: [
				"meta.parameters",
				"meta.type.parameters",
				"meta.return.type",
				"entity.name.type.interface",
				"meta.type.annotation",
			],
			settings: { fontStyle: "italic" },
		},
		{
			scope: ["markup.bold.markdown"],
			settings: { fontStyle: "bold" },
		},
	],
};
