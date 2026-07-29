import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import yaml from "js-yaml";

export const runtime = "nodejs";

export async function GET() {
  const file = path.join(process.cwd(), "public", "openapi.json");
  const json = JSON.parse(fs.readFileSync(file, "utf8"));
  const dumped = yaml.dump(json, { lineWidth: 120, noRefs: true });
  return new NextResponse(dumped, {
    headers: {
      "Content-Type": "application/yaml; charset=utf-8",
      "Content-Disposition": 'attachment; filename="thtwaat-openapi.yaml"'
    }
  });
}
