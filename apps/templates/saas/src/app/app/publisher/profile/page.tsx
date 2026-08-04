"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError } from "@/lib/api";
import { agentStoreApi } from "@/lib/services";
import { PageHeader, EmptyState } from "@/components/ui/misc";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PublisherNav, slugify } from "@/components/publisher/nav";

export default function PublisherProfilePage() {
  const qc = useQueryClient();
  const me = useQuery({
    queryKey: ["publisher-me"],
    queryFn: () => agentStoreApi.getMe(),
    retry: false
  });

  const [displayName, setDisplayName] = useState("");
  const [slug, setSlug] = useState("");
  const [bio, setBio] = useState("");
  const [website, setWebsite] = useState("");
  const [logoUrl, setLogoUrl] = useState("");
  const [bannerUrl, setBannerUrl] = useState("");
  const [github, setGithub] = useState("");
  const [linkedin, setLinkedin] = useState("");
  const [twitter, setTwitter] = useState("");

  const missing = me.isError && me.error instanceof ApiError && me.error.status === 404;

  useEffect(() => {
    if (!me.data) return;
    setDisplayName(me.data.display_name);
    setSlug(me.data.slug);
    setBio(me.data.bio || "");
    setWebsite(me.data.website || "");
    setLogoUrl(me.data.logo_url || "");
    setBannerUrl(me.data.banner_url || "");
    setGithub(me.data.github_url || "");
    setLinkedin(me.data.linkedin_url || "");
    setTwitter(me.data.twitter_url || "");
  }, [me.data]);

  const saveMut = useMutation({
    mutationFn: () =>
      agentStoreApi.upsertMe({
        display_name: displayName.trim(),
        slug: slugify(slug || displayName),
        bio: bio || null,
        website: website || null,
        logo_url: logoUrl || null,
        banner_url: bannerUrl || null,
        github_url: github || null,
        linkedin_url: linkedin || null,
        twitter_url: twitter || null
      }),
    onSuccess: (data) => {
      toast.success(missing ? "Publisher profile created" : "Profile saved");
      qc.setQueryData(["publisher-me"], data);
      qc.invalidateQueries({ queryKey: ["publisher-me"] });
    },
    onError: (e: Error) => toast.error(e.message)
  });

  return (
    <div className="space-y-6">
      <PageHeader
        title="Publisher Profile"
        description="Public identity shown on your marketplace pages."
        action={
          slug ? (
            <Link href={`/app/publishers/${slug}`} className="text-sm font-medium text-teal-700 hover:underline">
              Preview public page →
            </Link>
          ) : null
        }
      />
      <PublisherNav />

      {me.isError && !missing ? (
        <EmptyState title="Failed to load profile" description={(me.error as Error).message} />
      ) : (
        <Card className="grid gap-4 p-6 md:grid-cols-2">
          {missing ? (
            <p className="md:col-span-2 text-sm text-muted">
              You do not have a publisher profile yet. Fill this form to register.
            </p>
          ) : null}
          <label className="space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">
              Display name
            </span>
            <Input
              value={displayName}
              onChange={(e) => {
                const v = e.target.value;
                setDisplayName(v);
                if (!me.data) setSlug(slugify(v));
              }}
            />
          </label>
          <label className="space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">Slug</span>
            <Input value={slug} onChange={(e) => setSlug(slugify(e.target.value))} />
          </label>
          <label className="space-y-1.5 md:col-span-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">Bio</span>
            <textarea
              className="min-h-24 w-full rounded-xl border border-line bg-panel px-3 py-2 text-sm"
              value={bio}
              onChange={(e) => setBio(e.target.value)}
            />
          </label>
          <label className="space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">Website</span>
            <Input value={website} onChange={(e) => setWebsite(e.target.value)} />
          </label>
          <label className="space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">Avatar / logo</span>
            <Input value={logoUrl} onChange={(e) => setLogoUrl(e.target.value)} />
          </label>
          <label className="space-y-1.5 md:col-span-2">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">Banner</span>
            <Input value={bannerUrl} onChange={(e) => setBannerUrl(e.target.value)} />
          </label>
          <label className="space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">GitHub</span>
            <Input value={github} onChange={(e) => setGithub(e.target.value)} />
          </label>
          <label className="space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">LinkedIn</span>
            <Input value={linkedin} onChange={(e) => setLinkedin(e.target.value)} />
          </label>
          <label className="space-y-1.5">
            <span className="text-xs font-medium uppercase tracking-wide text-muted">Twitter / X</span>
            <Input value={twitter} onChange={(e) => setTwitter(e.target.value)} />
          </label>
          <div className="md:col-span-2">
            <Button onClick={() => saveMut.mutate()} disabled={saveMut.isPending || !displayName.trim()}>
              {missing ? "Create publisher profile" : "Save profile"}
            </Button>
          </div>
        </Card>
      )}
    </div>
  );
}
