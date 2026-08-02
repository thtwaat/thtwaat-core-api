export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type CodeSnippets = {
  curl: string;
  javascript: string;
  python: string;
  nodejs: string;
};

export function generateSnippets(opts: {
  method: HttpMethod;
  path: string;
  baseUrl: string;
  apiKey?: string;
  bearer?: string;
  body?: unknown;
}): CodeSnippets {
  const url = `${opts.baseUrl.replace(/\/$/, "")}${opts.path.startsWith("/") ? opts.path : `/${opts.path}`}`;
  const method = opts.method.toUpperCase() as HttpMethod;
  const hasBody = ["POST", "PUT", "PATCH"].includes(method) && opts.body !== undefined;
  const bodyJson = hasBody ? JSON.stringify(opts.body, null, 2) : "";

  const authHeader = opts.apiKey
    ? `X-API-Key: ${opts.apiKey}`
    : opts.bearer
      ? `Authorization: Bearer ${opts.bearer}`
      : "Authorization: Bearer <token>";

  const curl = [
    `curl -X ${method} '${url}' \\`,
    `  -H 'Content-Type: application/json' \\`,
    `  -H '${authHeader}'${hasBody ? " \\" : ""}`,
    hasBody ? `  -d '${bodyJson.replace(/'/g, "'\\''")}'` : ""
  ]
    .filter(Boolean)
    .join("\n");

  const javascript = `const res = await fetch("${url}", {
  method: "${method}",
  headers: {
    "Content-Type": "application/json",
    ${opts.apiKey ? `"X-API-Key": "${opts.apiKey}"` : `"Authorization": "Bearer ${opts.bearer || "<token>"}"`}
  }${hasBody ? `,\n  body: JSON.stringify(${bodyJson})` : ""}
});
const data = await res.json();
console.log(data);`;

  const nodejs = `import { RestClient } from "@thtwaat/rest";

const api = new RestClient({
  apiUrl: "${opts.baseUrl}",
  ${opts.apiKey ? `apiKey: "${opts.apiKey}"` : `/* setBearerToken after login */`}
});

// Example — prefer typed resource methods when available
const res = await fetch("${url}", {
  method: "${method}",
  headers: {
    "Content-Type": "application/json",
    ${opts.apiKey ? `"X-API-Key": process.env.THTWAAT_API_KEY!` : `"Authorization": \`Bearer \${process.env.THTWAAT_TOKEN}\``}
  }${hasBody ? `,\n  body: JSON.stringify(${bodyJson})` : ""}
});
console.log(await res.json());`;

  const python = `import requests

url = "${url}"
headers = {
    "Content-Type": "application/json",
    ${opts.apiKey ? `"X-API-Key": "${opts.apiKey}"` : `"Authorization": "Bearer <token>"`}
}
${hasBody ? `payload = ${bodyJson}\nresponse = requests.request("${method}", url, headers=headers, json=payload)` : `response = requests.request("${method}", url, headers=headers)`}
print(response.status_code, response.json())`;

  return { curl, javascript, python, nodejs };
}
