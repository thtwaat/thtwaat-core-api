"use client";

import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { agentsApi } from "@/lib/services";
import { agentSchema } from "@/lib/validators";
import { PageHeader } from "@/components/ui/misc";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/input";
import type { z } from "zod";

type FormValues = z.infer<typeof agentSchema>;

export default function NewAgentPage() {
  const router = useRouter();
  const form = useForm<FormValues>({
    resolver: zodResolver(agentSchema),
    defaultValues: {
      temperature: 0.7,
      system_prompt_template: "You are a helpful AI assistant for our product. Be concise and accurate."
    }
  });

  async function onSubmit(values: FormValues) {
    try {
      const agent = await agentsApi.create(values);
      toast.success("Agent created");
      router.push(`/app/agents/${agent.id}`);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not create agent");
    }
  }

  return (
    <div className="mx-auto max-w-2xl">
      <PageHeader title="Create agent" description="Draft agent connected to /v2/agents" />
      <Card>
        <form className="space-y-4" onSubmit={form.handleSubmit(onSubmit)}>
          <div>
            <Label>Name</Label>
            <Input {...form.register("name")} placeholder="Support Copilot" />
          </div>
          <div>
            <Label>Description</Label>
            <Input {...form.register("description")} />
          </div>
          <div>
            <Label>System prompt</Label>
            <Textarea {...form.register("system_prompt_template")} />
          </div>
          <div>
            <Label>Temperature</Label>
            <Input type="number" step="0.1" {...form.register("temperature")} />
          </div>
          <Button disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Creating…" : "Create agent"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
