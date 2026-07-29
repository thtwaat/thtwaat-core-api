import express from "express";
import { THTWAAT } from "@thtwaat/sdk";

const app = express();
app.use(express.json());

const client = new THTWAAT({
  apiKey: process.env.THTWAAT_API_KEY!,
  apiUrl: process.env.THTWAAT_API_URL || "http://localhost:8000",
});

app.post("/ask", async (req, res) => {
  try {
    const result = await client.chat({
      message: String(req.body.message || ""),
      sessionId: req.body.sessionId,
      metadata: { source: "express" },
    });
    res.json(result);
  } catch (e: any) {
    res.status(e.status || 500).json({ error: e.message });
  }
});

app.listen(3080, () => console.log("http://localhost:3080"));
