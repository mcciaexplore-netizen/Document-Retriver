"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, json } from "@/lib/api";

export default function SsoCallbackPage() {
  const router = useRouter();
  const [message, setMessage] = useState("Signing you in...");
  const completed = useRef(false);

  useEffect(() => {
    if (completed.current) return;
    completed.current = true;
    const params = new URLSearchParams(window.location.search);
    const code = params.get("code") ?? "";
    const state = params.get("state") ?? "";
    const expectedState = localStorage.getItem("evidence-vault-sso-state");
    localStorage.removeItem("evidence-vault-sso-state");
    window.history.replaceState({}, "", "/sso/callback");
    if (!code || !state || !expectedState || state !== expectedState) {
      setMessage("This sign-in link is invalid or has expired. Return to the CRM and try again.");
      return;
    }

    api("/auth/sso", json({ code, state }))
      .then(() => router.replace("/"))
      .catch(() => {
        setMessage("Your account could not be signed in. Contact your administrator to enable Evidence Vault access.");
      });
  }, [router]);

  return (
    <main className="grid min-h-dvh place-items-center px-6 text-center" aria-live="polite">
      <p className="max-w-md text-sm text-slate-700">{message}</p>
    </main>
  );
}
