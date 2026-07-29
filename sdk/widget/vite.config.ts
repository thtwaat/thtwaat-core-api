import { defineConfig } from "vite";
import { resolve } from "path";
import { copyFileSync, mkdirSync, existsSync, writeFileSync, readFileSync } from "fs";

function copyToApiStatic() {
  return {
    name: "copy-to-api-static",
    closeBundle() {
      const dist = resolve(__dirname, "dist");
      const target = resolve(__dirname, "../../app/agent_platform/static/widget");
      mkdirSync(target, { recursive: true });

      const iife = resolve(dist, "widget.iife.js");
      const css = resolve(dist, "widget.css");
      if (existsSync(iife)) {
        copyFileSync(iife, resolve(target, "widget.js"));
        copyFileSync(iife, resolve(dist, "widget.cdn.js"));
      }
      if (existsSync(css)) {
        copyFileSync(css, resolve(target, "widget.css"));
      }

      if (existsSync(resolve(target, "widget.js"))) {
        const bytes = readFileSync(resolve(target, "widget.js")).byteLength;
        writeFileSync(resolve(target, "SIZE.txt"), `widget.js bytes=${bytes}\n`);
      }
    },
  };
}

export default defineConfig({
  build: {
    lib: {
      entry: resolve(__dirname, "src/index.ts"),
      name: "THTWAAT",
      formats: ["iife", "es", "umd"],
      fileName: (format) => {
        if (format === "iife") return "widget.iife.js";
        if (format === "umd") return "widget.umd.cjs";
        return "widget.js";
      },
    },
    cssCodeSplit: false,
    sourcemap: true,
    minify: "esbuild",
    target: "es2018",
    rollupOptions: {
      output: {
        assetFileNames: "widget.[ext]",
        inlineDynamicImports: true,
        extend: true,
      },
    },
  },
  plugins: [copyToApiStatic()],
});
