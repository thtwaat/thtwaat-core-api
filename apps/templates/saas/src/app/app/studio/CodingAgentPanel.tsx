"use client";

// Coding AI — submit a natural-language coding task to the existing
// app/coding_agent proxy (AI_Project's AgentRuntime, unmodified by this
// panel). A separate entry point from the AI Software Factory build flow
// and from THTWAAT Deploy above; does not touch GitHub, Preview, or billing
// state. Project selection here is UI-only labeling — Core's coding-agent
// API has no project field; AI_Project derives the actual workspace from
// the authenticated identity alone. There is no list-tasks endpoint, so
// this panel tracks a single active task, persisted to localStorage so a
// page reload resumes watching it.

import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { useAuth } from "@/lib/auth";
import { canUseCodingAgent } from "@/lib/permissions";
import { codingAgentApi, studioApi } from "@/lib/services";
import {
  clearActiveTask,
  codingTaskStatusLabel,
  codingTaskStatusTone,
  generateIdempotencyKey,
  isTerminalStatus,
  readActiveTask,
  shouldContinuePolling,
  summarizeCodingResult,
  writeActiveTask
} from "@/lib/coding-agent";
import { Card, CardHeader, Badge } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label, Select, Textarea } from "@/components/ui/input";

const MAX_GOAL_CHARS = 20_000;

export function CodingAgentPanel() {
  const { user } = useAuth();
  const canUse = canUseCodingAgent(user?.role);
  const qc = useQueryClient();

  const initial = readActiveTask();
  const [goal, setGoal] = useState("");
  const [projectId, setProjectId] = useState<string>(initial?.projectId ?? "");
  const [activeTaskId, setActiveTaskId] = useState<string | null>(initial?.taskId ?? null);
  const submitKeyRef = useRef<string>("");

  const projects = useQuery({ queryKey: ["studio-projects"], queryFn: () => studioApi.list() });
  const activeProjectId = projectId || projects.data?.items?.[0]?.id || "";

  const taskQ = useQuery({
    queryKey: ["coding-agent-task", activeTaskId],
    queryFn: () => codingAgentApi.getTask(activeTaskId as string),
    enabled: Boolean(activeTaskId),
    refetchInterval: (q) => {
      if (q.state.error) return false;
      const status = q.state.data?.status;
      if (!status) return 4000;
      return shouldContinuePolling(status, q.state.dataUpdateCount) ? 4000 : false;
    }
  });

  const createM = useMutation({
    mutationFn: () =>
      codingAgentApi.createTask({ goal: goal.trim() }, submitKeyRef.current || generateIdempotencyKey()),
    onSuccess: (task) => {
      writeActiveTask({ taskId: task.task_id, projectId: activeProjectId || null, createdAt: Date.now() });
      setActiveTaskId(task.task_id);
      qc.setQueryData(["coding-agent-task", task.task_id], task);
      toast.success("Coding task submitted");
    },
    onError: (e: Error) => toast.error(e.message || "Failed to submit task")
  });

  const cancelM = useMutation({
    mutationFn: () => codingAgentApi.cancelTask(activeTaskId as string),
    onSuccess: () => {
      toast.message("Cancellation requested");
      qc.invalidateQueries({ queryKey: ["coding-agent-task", activeTaskId] });
    },
    onError: (e: Error) => toast.error(e.message || "Failed to cancel task")
  });

  if (!canUse) return null;

  const task = taskQ.data;
  const hasTerminalOrNoTask = !activeTaskId || (task ? isTerminalStatus(task.status) : false);

  function submit() {
    if (!goal.trim()) return;
    submitKeyRef.current = generateIdempotencyKey();
    createM.mutate();
  }

  function startNew() {
    clearActiveTask();
    setActiveTaskId(null);
    setGoal("");
  }

  return (
    <Card>
      <CardHeader
        title="Coding AI"
        description="Describe a coding task in plain language — it runs against your connected workspace."
      />

      {projects.data && projects.data.items.length > 1 && (
        <div className="mb-4">
          <Label htmlFor="coding-agent-project-select">Project (for your reference only)</Label>
          <Select
            id="coding-agent-project-select"
            value={activeProjectId}
            onChange={(e) => setProjectId(e.target.value)}
          >
            {projects.data.items.map((p) => (
              <option key={p.id} value={p.id}>
                {p.title}
              </option>
            ))}
          </Select>
        </div>
      )}

      {hasTerminalOrNoTask && (
        <div>
          <Label htmlFor="coding-agent-goal">What do you want built?</Label>
          <Textarea
            id="coding-agent-goal"
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            maxLength={MAX_GOAL_CHARS}
            placeholder="e.g. Add a dark mode toggle to the settings page"
            disabled={createM.isPending}
            aria-label="Coding task description"
          />
          <div className="mt-3 flex items-center justify-between">
            <p className="text-xs text-muted">{goal.length}/{MAX_GOAL_CHARS}</p>
            <Button onClick={submit} disabled={!goal.trim() || createM.isPending}>
              Submit task
            </Button>
          </div>
        </div>
      )}

      {activeTaskId && (
        <div className="mt-6 rounded-2xl border border-line bg-canvas p-4">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Badge tone={codingTaskStatusTone(task?.status ?? "queued")}>
                {codingTaskStatusLabel(task?.status ?? "queued")}
              </Badge>
              {task?.phase && <span className="text-xs text-muted">{task.phase}</span>}
            </div>
            <div className="flex items-center gap-2">
              {task && !isTerminalStatus(task.status) && (
                <Button size="sm" variant="secondary" onClick={() => cancelM.mutate()} disabled={cancelM.isPending}>
                  Cancel
                </Button>
              )}
              {task && isTerminalStatus(task.status) && (
                <Button size="sm" variant="ghost" onClick={startNew}>
                  Start new task
                </Button>
              )}
            </div>
          </div>

          {taskQ.error && (
            <p className="mt-3 text-sm text-red-600">
              {taskQ.error instanceof Error ? taskQ.error.message : "Could not load task status."}
            </p>
          )}

          {task?.result != null && (
            <pre className="mt-3 whitespace-pre-wrap break-words rounded-xl bg-white p-3 text-xs text-ink">
              {summarizeCodingResult(task.result)}
            </pre>
          )}

          {task?.error != null && (
            <pre className="mt-3 whitespace-pre-wrap break-words rounded-xl bg-red-50 p-3 text-xs text-red-700">
              {summarizeCodingResult(task.error)}
            </pre>
          )}
        </div>
      )}
    </Card>
  );
}
