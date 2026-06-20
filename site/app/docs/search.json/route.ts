import { docsSearchRecords } from "../../../content/docs/pages";

export const dynamic = "force-static";

export function GET() {
  return Response.json({
    generatedAt: "build-time",
    records: docsSearchRecords()
  });
}
