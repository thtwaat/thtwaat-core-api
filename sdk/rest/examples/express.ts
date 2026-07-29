import express from "express";
import { RestClient } from "@thtwaat/rest";

const app = express();
app.use(express.json());

const api = new RestClient({
  apiUrl: process.env.THTWAAT_API_URL || "http://localhost:8000",
  bearerToken: process.env.THTWAAT_JWT,
});

app.get("/plans", async (_req, res) => {
  res.json(await api.billing.listPlans());
});

app.listen(3090);
