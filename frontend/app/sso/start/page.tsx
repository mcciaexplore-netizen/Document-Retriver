"use client";

import { useEffect, useRef, useState } from "react";

const CRM_API_URL = (process.env.NEXT_PUBLIC_CRM_API_URL || "https://gen-crm.onrender.com/api").replace(/\/+$/, "");

export default function SsoStartPage() {
  const [message, setMessage] = useState("Connecting to your CRM account...");
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    if (!CRM_API_URL) {
      setMessage("CRM sign-in is not configured. Contact your administrator.");
      return;
    }

    const state = crypto.randomUUID().replaceAll("-", "");
    localStorage.setItem("evidence-vault-sso-state", state);
    const launchUrl = new URL(
      `${CRM_API_URL.replace(/\/+$/, "")}/auth/evidence-vault/launch`,
    );
    launchUrl.searchParams.set("state", state);
    window.location.assign(launchUrl.toString());
  }, []);

  return (
    <main className="grid min-h-dvh place-items-center px-6 text-center" aria-live="polite">
      <p className="max-w-md text-sm text-slate-700">{message}</p>
    </main>
  );
}