import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const runtime = "nodejs";

type OpenApi = {
  info?: { title?: string; version?: string; description?: string };
  servers?: Array<{ url?: string }>;
  paths?: Record<string, Record<string, { summary?: string; operationId?: string; requestBody?: unknown }>>;
};

export async function GET() {
  const file = path.join(process.cwd(), "public", "openapi.json");
  const spec = JSON.parse(fs.readFileSync(file, "utf8")) as OpenApi;
  const base = spec.servers?.[0]?.url || "{{baseUrl}}";

  const items: Array<Record<string, unknown>> = [];
  for (const [p, methods] of Object.entries(spec.paths || {})) {
    for (const [method, op] of Object.entries(methods || {})) {
      if (!["get", "post", "put", "patch", "delete"].includes(method)) continue;
      items.push({
        name: op.summary || op.operationId || `${method.toUpperCase()} ${p}`,
        request: {
          method: method.toUpperCase(),
          header: [
            { key: "Content-Type", value: "application/json" },
            { key: "Authorization", value: "Bearer {{token}}" }
          ],
          url: {
            raw: `${base}${p}`,
            host: ["{{baseUrl}}"],
            path: p.replace(/^\//, "").split("/")
          },
          body: op.requestBody
            ? {
                mode: "raw",
                raw: JSON.stringify({ example: true }, null, 2),
                options: { raw: { language: "json" } }
              }
            : undefined
        }
      });
    }
  }

  const collection = {
    info: {
      name: spec.info?.title || "THTWAAT Core API",
      description: spec.info?.description || "Generated from OpenAPI",
      schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json",
      version: spec.info?.version || "1.0.0"
    },
    variable: [
      { key: "baseUrl", value: base },
      { key: "token", value: "" },
      { key: "apiKey", value: "" }
    ],
    item: items
  };

  return NextResponse.json(collection, {
    headers: {
      "Content-Disposition": 'attachment; filename="thtwaat-postman-collection.json"'
    }
  });
}
