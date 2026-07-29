import { RestClient } from "@thtwaat/rest";

async function main() {
  const api = new RestClient({
    apiUrl: process.env.THTWAAT_API_URL || "http://localhost:8000",
    apiKey: process.env.THTWAAT_API_KEY,
  });

  const res = await api.agents.chat({ message: process.argv[2] || "Hello" });
  console.log(res);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
