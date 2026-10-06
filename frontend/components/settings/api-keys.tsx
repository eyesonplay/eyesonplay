"use client";

import { Check, Copy, KeyRound, Loader2, Plus } from "lucide-react";
import { type FormEvent, useState } from "react";
import { toast } from "sonner";

import { ConfirmDialog } from "@/components/common/confirm-dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiKeys, useCreateApiKey, useRevokeApiKey } from "@/hooks/queries";
import { type ApiKey, type ApiKeyCreated, errorMessage } from "@/lib/api";
import { formatDateTime } from "@/lib/format";

/** Integration feed keys: create (shown once), list, revoke. */
export function ApiKeysSection() {
  const keys = useApiKeys();
  const [created, setCreated] = useState<ApiKeyCreated | null>(null);

  return (
    <section className="flex flex-col gap-4 rounded-lg border bg-card p-5">
      <div>
        <h2 className="flex items-center gap-2 text-sm font-medium">
          <KeyRound className="size-4 text-muted-foreground" /> API keys
        </h2>
        <p className="mt-1 text-xs text-muted-foreground">
          For other systems reading matches and live events through the integration feed (
          <code className="font-mono">X-API-Key</code> header). A key is shown once, when it is created.
        </p>
      </div>
      <CreateKeyForm onCreated={setCreated} />
      {created ? <NewKey created={created} onDone={() => setCreated(null)} /> : null}
      {keys.isError ? (
        <p className="text-sm text-destructive">{errorMessage(keys.error)}</p>
      ) : !keys.data ? (
        <Skeleton className="h-16" />
      ) : keys.data.length === 0 ? (
        <p className="text-xs text-muted-foreground">No keys yet.</p>
      ) : (
        <ul className="flex flex-col divide-y rounded-lg border">
          {keys.data.map((key) => (
            <KeyRow key={key.id} apiKey={key} />
          ))}
        </ul>
      )}
    </section>
  );
}

function CreateKeyForm({ onCreated }: { onCreated: (key: ApiKeyCreated) => void }) {
  const create = useCreateApiKey();
  const [name, setName] = useState("");

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate(name.trim(), {
      onSuccess: (key) => {
        setName("");
        onCreated(key);
      },
      onError: (error) => toast.error("Could not create the key", { description: errorMessage(error) }),
    });
  }

  return (
    <form onSubmit={submit} className="flex gap-2">
      <Input
        value={name}
        onChange={(e) => setName(e.target.value)}
        placeholder="Name, e.g. the system that will use it"
        maxLength={120}
        aria-label="New API key name"
      />
      <Button type="submit" disabled={create.isPending || !name.trim()}>
        {create.isPending ? <Loader2 className="animate-spin" /> : <Plus />} Create
      </Button>
    </form>
  );
}

function NewKey({ created, onDone }: { created: ApiKeyCreated; onDone: () => void }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(created.key);
      setCopied(true);
    } catch {
      toast.error("Copy failed: select the key and copy it manually");
    }
  }

  return (
    <div role="status" className="flex flex-col gap-2 rounded-lg border border-primary/40 bg-primary/5 p-3">
      <p className="text-xs">
        Copy the key for <strong>{created.name}</strong> now. It will not be shown again.
      </p>
      <div className="flex gap-2">
        <code className="min-w-0 flex-1 truncate rounded bg-background px-2 py-1.5 font-mono text-xs select-all">
          {created.key}
        </code>
        <Button size="sm" variant="outline" onClick={copy}>
          {copied ? <Check /> : <Copy />} {copied ? "Copied" : "Copy"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onDone}>
          Done
        </Button>
      </div>
    </div>
  );
}

function KeyRow({ apiKey }: { apiKey: ApiKey }) {
  const revoke = useRevokeApiKey();
  const revoked = apiKey.revoked_at !== null;
  return (
    <li className="flex items-center justify-between gap-3 px-3 py-2.5 text-sm">
      <div className="min-w-0">
        <div className="flex items-center gap-2">
          <span className="truncate font-medium">{apiKey.name}</span>
          <code className="font-mono text-xs text-muted-foreground">{apiKey.prefix}…</code>
          {revoked ? <span className="text-xs text-destructive">revoked</span> : null}
        </div>
        <p className="text-xs text-muted-foreground">
          Created {formatDateTime(apiKey.created_at)} · last used{" "}
          {apiKey.last_used_at ? formatDateTime(apiKey.last_used_at) : "never"}
        </p>
      </div>
      {revoked ? null : (
        <ConfirmDialog
          trigger={
            <Button size="sm" variant="outline" disabled={revoke.isPending}>
              Revoke
            </Button>
          }
          title={`Revoke "${apiKey.name}"?`}
          description="Systems using this key lose access immediately. This cannot be undone."
          confirmLabel="Revoke key"
          destructive
          onConfirm={() =>
            revoke.mutate(apiKey.id, {
              onSuccess: () => toast.success("Key revoked"),
              onError: (error) => toast.error("Could not revoke the key", { description: errorMessage(error) }),
            })
          }
        />
      )}
    </li>
  );
}
