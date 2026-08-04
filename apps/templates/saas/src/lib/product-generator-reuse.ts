/**
 * Product Generator — detect idempotent "template already installed" reuse responses.
 */
export type ProductReuseLinks = {
  agentHref: string | null;
  knowledgeHref: string | null;
  widgetHref: string | null;
  continueHref: string;
};

export const REUSE_EXISTING_TOAST =
  "Template already installed.\nOpening your existing AI workspace.";

export function isAlreadyInstalledGeneration(gen: {
  already_installed?: boolean;
  result?: Record<string, unknown> | null;
}): boolean {
  if (gen.already_installed === true) return true;
  return Boolean(gen.result && gen.result.already_installed === true);
}

export function reuseMessageFor(gen: {
  reuse_message?: string | null;
  result?: Record<string, unknown> | null;
}): string {
  if (typeof gen.reuse_message === "string" && gen.reuse_message.trim()) {
    return gen.reuse_message;
  }
  const fromResult = gen.result?.reuse_message;
  if (typeof fromResult === "string" && fromResult.trim()) return fromResult;
  return REUSE_EXISTING_TOAST.replace("\n", " ");
}

export function productReuseLinks(gen: {
  agent_id?: string | null;
  knowledge_base_id?: string | null;
  widget_id?: string | null;
  id?: string;
}): ProductReuseLinks {
  return {
    agentHref: gen.agent_id ? `/app/agents/${encodeURIComponent(gen.agent_id)}` : "/app/agents",
    knowledgeHref: gen.knowledge_base_id
      ? `/app/knowledge?kb=${encodeURIComponent(gen.knowledge_base_id)}`
      : "/app/knowledge",
    widgetHref: gen.agent_id
      ? `/app/agents/${encodeURIComponent(gen.agent_id)}?tab=widget`
      : "/app/publish",
    continueHref: gen.id
      ? `/app/create?generation=${encodeURIComponent(gen.id)}`
      : "/app/create",
  };
}
