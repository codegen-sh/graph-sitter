import { getDocsSearchIndex } from "@/lib/docs";

export const dynamic = "force-static";

export function GET() {
  return Response.json({
    generatedAt: "build-time",
    records: getDocsSearchIndex()
  });
}
