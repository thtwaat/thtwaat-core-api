"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { domainsApi } from "@/lib/services";
import { domainSchema } from "@/lib/validators";
import { formatDate } from "@/lib/utils";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Badge, Card, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input, Label, Select } from "@/components/ui/input";
import type { z } from "zod";

type FormValues = z.infer<typeof domainSchema>;

export default function DomainsPage() {
  const qc = useQueryClient();
  const domains = useQuery({ queryKey: ["domains"], queryFn: domainsApi.list });
  const form = useForm<FormValues>({
    resolver: zodResolver(domainSchema),
    defaultValues: { verification_method: "TXT", is_primary: false }
  });

  const create = useMutation({
    mutationFn: (values: FormValues) => domainsApi.create(values),
    onSuccess: () => {
      toast.success("Domain added");
      form.reset({ verification_method: "TXT", is_primary: false, hostname: "" });
      qc.invalidateQueries({ queryKey: ["domains"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const verify = useMutation({
    mutationFn: (id: string) => domainsApi.verify(id),
    onSuccess: () => {
      toast.success("Verification attempted");
      qc.invalidateQueries({ queryKey: ["domains"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const retry = useMutation({
    mutationFn: (id: string) => domainsApi.retry(id),
    onSuccess: () => {
      toast.success("Retry queued");
      qc.invalidateQueries({ queryKey: ["domains"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const ssl = useMutation({
    mutationFn: (id: string) => domainsApi.sslRequest(id),
    onSuccess: (data: { message?: string; ssl_status?: string }) => {
      toast.success(data?.message || "SSL certificate issued");
      qc.invalidateQueries({ queryKey: ["domains"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const remove = useMutation({
    mutationFn: (id: string) => domainsApi.remove(id),
    onSuccess: () => {
      toast.success("Domain deleted");
      qc.invalidateQueries({ queryKey: ["domains"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  const list = Array.isArray(domains.data) ? domains.data : [];

  return (
    <div className="space-y-6">
      <PageHeader title="Domains" description="Add, verify, request SSL, retry, and delete custom domains." />

      <Card>
        <CardHeader title="Add domain" />
        <form className="grid gap-3 md:grid-cols-4" onSubmit={form.handleSubmit((v) => create.mutate(v))}>
          <div className="md:col-span-2">
            <Label>Hostname</Label>
            <Input placeholder="chat.acme.com" {...form.register("hostname")} />
          </div>
          <div>
            <Label>Method</Label>
            <Select {...form.register("verification_method")}>
              <option value="TXT">TXT</option>
              <option value="CNAME">CNAME</option>
            </Select>
          </div>
          <div className="flex items-end">
            <Button className="w-full" disabled={create.isPending}>Add</Button>
          </div>
        </form>
      </Card>

      {!list.length && !domains.isLoading && (
        <EmptyState title="No domains yet" description="Add a hostname to begin DNS verification." />
      )}

      <div className="grid gap-4">
        {list.map((domain) => {
          const pendingDns = ["PENDING", "DNS_PENDING", "FAILED"].includes(String(domain.status));
          return (
          <Card key={domain.id}>
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="font-semibold">{domain.hostname}</h3>
                  <Badge tone={domain.status === "LIVE" || domain.status === "VERIFIED" ? "success" : "warn"}>
                    {domain.status}
                  </Badge>
                  <Badge>SSL {domain.ssl_status}</Badge>
                </div>
                <p className="mt-2 text-xs text-muted">Added {formatDate(domain.created_at)}</p>
                {pendingDns && (
                  <p className="mt-2 text-sm text-amber-700">
                    Add the DNS records below, then click Verify (or Request SSL to verify + issue in one step).
                  </p>
                )}
                {domain.failure_reason && <p className="mt-2 text-sm text-red-600">{domain.failure_reason}</p>}
                <div className="mt-3 space-y-1 text-xs text-muted">
                  {(domain.dns_records || []).slice(0, 3).map((r, i) => (
                    <p key={i}>
                      {String(r.type)} {String(r.host)} → {String(r.value)}
                    </p>
                  ))}
                  <p>Token: {domain.verification_token}</p>
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                <Button size="sm" variant="secondary" onClick={() => verify.mutate(domain.id)}>Verify</Button>
                <Button size="sm" variant="secondary" onClick={() => retry.mutate(domain.id)}>Retry</Button>
                <Button size="sm" disabled={ssl.isPending} onClick={() => ssl.mutate(domain.id)}>
                  Request SSL
                </Button>
                <Button size="sm" variant="danger" onClick={() => remove.mutate(domain.id)}>Delete</Button>
              </div>
            </div>
          </Card>
          );
        })}
      </div>
    </div>
  );
}
