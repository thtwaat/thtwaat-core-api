import { Injectable } from "@angular/core";

@Injectable({ providedIn: "root" })
export class ThtwaatWidgetService {
  private script?: HTMLScriptElement;

  load(apiKey: string, apiBaseUrl = "http://localhost:8000") {
    this.destroy();
    const s = document.createElement("script");
    s.src = `${apiBaseUrl}/widget.js`;
    s.dataset["apiKey"] = apiKey;
    s.dataset["theme"] = "light";
    s.dataset["position"] = "bottom-right";
    document.body.appendChild(s);
    this.script = s;
  }

  destroy() {
    (window as any).THTWAAT?.destroy?.();
    this.script?.remove();
    this.script = undefined;
  }
}
