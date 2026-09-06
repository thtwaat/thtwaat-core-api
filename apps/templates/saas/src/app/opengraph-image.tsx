import { ImageResponse } from "next/og";
import { site } from "@/lib/config";

export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpengraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: "80px",
          background: "#f8fafc",
          fontFamily: "sans-serif"
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            width: 64,
            height: 64,
            borderRadius: 16,
            background: site.brandColor,
            color: "#ffffff",
            fontSize: 32,
            fontWeight: 700,
            marginBottom: 40
          }}
        >
          T
        </div>
        <div style={{ display: "flex", fontSize: 56, fontWeight: 700, color: "#0f172a", lineHeight: 1.2 }}>
          {site.tagline}
        </div>
        <div style={{ display: "flex", fontSize: 28, color: "#64748b", marginTop: 24, maxWidth: 900 }}>
          {site.description}
        </div>
      </div>
    ),
    { ...size }
  );
}
