import type { Metadata } from "next";
import { Suspense } from "react";

import { LoginForm } from "@/components/auth/login-form";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Sign in" };

export default function LoginPage() {
  return (
    <main className="grid min-h-screen place-items-center px-4">
      <Card className="w-full max-w-sm">
        <CardHeader>
          <div className="mb-2 flex items-center gap-2.5">
            <span className="grid size-7 place-items-center rounded-md bg-primary/15 ring-1 ring-primary/30">
              <span className="size-2.5 rounded-full bg-primary shadow-[0_0_12px] shadow-primary/60" />
            </span>
            <span className="text-sm font-semibold tracking-tight">EyesOnPlay</span>
          </div>
          <CardTitle>Sign in</CardTitle>
          <CardDescription>Use the account your administrator created.</CardDescription>
        </CardHeader>
        <CardContent>
          {/* useSearchParams (the return path) needs a Suspense boundary when prerendered. */}
          <Suspense fallback={null}>
            <LoginForm />
          </Suspense>
        </CardContent>
      </Card>
    </main>
  );
}
