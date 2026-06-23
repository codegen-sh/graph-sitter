import { ImageResponse } from "next/og";

export const alt = "Graph-sitter — industrial-grade static analysis toolkit";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

const WIDTH = 1200;
const HEIGHT = 630;

// Deterministic node-graph laid out mostly to the right so it reads as a
// network behind the wordmark without fighting the text on the left.
const nodes: { x: number; y: number; r: number; c: string; o: number }[] = [
	{ x: 120, y: 92, r: 5, c: "#a277ff", o: 0.5 },
	{ x: 78, y: 520, r: 6, c: "#82e2ff", o: 0.45 },
	{ x: 300, y: 560, r: 5, c: "#61ffca", o: 0.5 },
	{ x: 760, y: 92, r: 7, c: "#a277ff", o: 0.95 },
	{ x: 900, y: 168, r: 9, c: "#82e2ff", o: 0.95 },
	{ x: 1044, y: 110, r: 6, c: "#ffca85", o: 0.9 },
	{ x: 980, y: 300, r: 12, c: "#a277ff", o: 0.95 },
	{ x: 1124, y: 380, r: 7, c: "#61ffca", o: 0.9 },
	{ x: 860, y: 432, r: 8, c: "#82e2ff", o: 0.95 },
	{ x: 1020, y: 520, r: 6, c: "#a277ff", o: 0.9 },
	{ x: 724, y: 560, r: 7, c: "#ffca85", o: 0.9 },
	{ x: 700, y: 300, r: 9, c: "#a277ff", o: 0.95 },
	{ x: 560, y: 198, r: 5, c: "#6f6b80", o: 0.6 },
	{ x: 600, y: 460, r: 6, c: "#82e2ff", o: 0.85 },
	{ x: 1140, y: 232, r: 5, c: "#6f6b80", o: 0.6 },
	{ x: 840, y: 250, r: 5, c: "#61ffca", o: 0.85 },
	{ x: 470, y: 92, r: 4, c: "#6f6b80", o: 0.5 },
	{ x: 432, y: 540, r: 5, c: "#a277ff", o: 0.7 },
];

const edges: [number, number][] = [
	[3, 4],
	[4, 5],
	[4, 6],
	[6, 7],
	[6, 8],
	[8, 9],
	[8, 10],
	[6, 11],
	[11, 3],
	[11, 15],
	[15, 4],
	[8, 13],
	[13, 10],
	[11, 12],
	[12, 16],
	[11, 5],
	[6, 14],
	[7, 9],
	[10, 9],
	[8, 15],
	[13, 17],
	[17, 2],
	[12, 0],
	[1, 17],
	[14, 7],
	[3, 15],
];

function networkDataUri() {
	const lines = edges
		.map(([a, b]) => {
			const p = nodes[a];
			const q = nodes[b];
			return `<line x1="${p.x}" y1="${p.y}" x2="${q.x}" y2="${q.y}" stroke="#8f74ff" stroke-width="1.4" stroke-opacity="0.42"/>`;
		})
		.join("");
	const dots = nodes
		.map(
			(n) =>
				`<circle cx="${n.x}" cy="${n.y}" r="${n.r}" fill="${n.c}" fill-opacity="${n.o}"/>`,
		)
		.join("");
	const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}"><defs><radialGradient id="glow" cx="32%" cy="42%" r="68%"><stop offset="0%" stop-color="#7c4dff" stop-opacity="0.42"/><stop offset="48%" stop-color="#7c4dff" stop-opacity="0.10"/><stop offset="100%" stop-color="#0a0a0f" stop-opacity="0"/></radialGradient></defs><rect width="${WIDTH}" height="${HEIGHT}" fill="#0a0a0f"/><rect width="${WIDTH}" height="${HEIGHT}" fill="url(#glow)"/><g>${lines}</g><g>${dots}</g></svg>`;
	return `data:image/svg+xml,${encodeURIComponent(svg)}`;
}

const markSvg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 80.87 80.87" fill="#ffffff"><path d="M57.34,27.51c-.79.79-.79,2.07,0,2.86l8.64,8.64c.79.79.79,2.07,0,2.86l-8.64,8.64c-.79.79-.79,2.07,0,2.86l4.29,4.29c.79.79,2.07.79,2.86,0l15.79-15.79c.79-.79.79-2.07,0-2.86l-15.79-15.79c-.79-.79-2.07-.79-2.86,0,0,0-4.29,4.29-4.29,4.29Z"/><path d="M50.19,60.51c-.79-.79-2.07-.79-2.86,0l-5.47,5.47c-.79.79-2.07.79-2.86,0l-24.12-24.12c-.79-.79-.79-2.07,0-2.86l24.12-24.12c.79-.79,2.07-.79,2.86,0l5.47,5.47c.79.79,2.07.79,2.86,0l4.29-4.29c.79-.79.79-2.07,0-2.86L41.86.59c-.79-.79-2.07-.79-2.86,0L.59,39.01c-.79.79-.79,2.07,0,2.86l38.41,38.41c.79.79,2.07.79,2.86,0l12.62-12.62c.79-.79.79-2.07,0-2.86,0,0-4.29-4.29-4.29-4.29Z"/><path d="M50.54,40.44c0,5.58-4.53,10.11-10.11,10.11s-10.11-4.53-10.11-10.11,4.53-10.11,10.11-10.11,10.11,4.53,10.11,10.11Z"/></svg>`;
const markUri = `data:image/svg+xml,${encodeURIComponent(markSvg)}`;

export default function OpengraphImage() {
	return new ImageResponse(
		<div
			style={{
				width: "100%",
				height: "100%",
				display: "flex",
				position: "relative",
				backgroundColor: "#0a0a0f",
			}}
		>
			{/* biome-ignore lint/a11y/useAltText: decorative background in OG image */}
			<img
				src={networkDataUri()}
				width={WIDTH}
				height={HEIGHT}
				style={{ position: "absolute", top: 0, left: 0 }}
			/>

			<div
				style={{
					display: "flex",
					flexDirection: "column",
					justifyContent: "center",
					height: "100%",
					padding: "0 96px",
				}}
			>
				<div style={{ display: "flex", alignItems: "center" }}>
					{/* biome-ignore lint/a11y/useAltText: decorative logo in OG image */}
					<img src={markUri} width={104} height={104} />
					<div
						style={{
							marginLeft: 36,
							fontSize: 98,
							fontWeight: 700,
							color: "#ffffff",
							letterSpacing: -3,
						}}
					>
						Graph-sitter
					</div>
				</div>
				<div
					style={{
						marginTop: 26,
						fontSize: 42,
						color: "#c4c1cc",
						letterSpacing: -0.5,
					}}
				>
					Industrial-grade static analysis toolkit
				</div>
			</div>
		</div>,
		{ ...size },
	);
}
