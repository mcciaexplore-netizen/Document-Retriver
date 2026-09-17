"use client";
import { useEffect, useState, FormEvent } from "react";
import {
  ChevronRight,
  ArrowRight,
  ShieldCheck,
  CheckCheck,
  LockKeyhole,
  FileSearch,
  Eye,
  EyeOff,
} from "lucide-react";
import { api, json, ApiError, backendConfigured } from "@/lib/api";
import { FileIcon, ErrorBox } from "@/components/ui";
import type { User } from "@/types";
import { Logo } from "@/components/shared";

type DemoAccount = { email: string; password: string; role: string };

export function Login({ onLogin }: { onLogin: (u: User) => void }) {
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState(""),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [showPassword, setShowPassword] = useState(false),
    [mode, setMode] = useState<"login" | "register">("login"),
    [name, setName] = useState(""),
    [confirmPassword, setConfirmPassword] = useState(""),
    [allowRegistration, setAllowRegistration] = useState(false),
    [demoAccounts, setDemoAccounts] = useState<DemoAccount[]>([]),
    [connectionError, setConnectionError] = useState(""),
    [optionsLoading, setOptionsLoading] = useState(true),
    [optionsAttempt, setOptionsAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setOptionsLoading(true);
    api<{ demo_accounts: DemoAccount[]; allow_registration: boolean }>(
      "/auth/options",
    )
      .then((options) => {
        if (active) {
          setDemoAccounts(options.demo_accounts);
          setAllowRegistration(options.allow_registration);
          setConnectionError("");
        }
      })
      .catch((e: Error) => {
        if (active) setConnectionError(e.message);
      })
      .finally(() => {
        if (active) setOptionsLoading(false);
      });
    return () => {
      active = false;
    };
  }, [optionsAttempt]);
  async function signIn(loginEmail: string, loginPassword: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    let credentialsAccepted = false;
    try {
      await api<{ user: User }>(
        "/auth/login",
        json({
          email: loginEmail.trim().toLowerCase(),
          password: loginPassword,
        }),
      );
      credentialsAccepted = true;
      const user = await api<User>("/auth/me");
      onLogin(user);
    } catch (e) {
      setError(
        e instanceof ApiError && e.status === 401
          ? credentialsAccepted
            ? "Your sign-in session could not be saved. Allow cookies for this site and try again."
            : `The email or password is incorrect. ${allowRegistration ? "New here? Choose Create account to register your email." : "Use an account created by your administrator."}`
          : (e as Error).message,
      );
    } finally {
      setBusy(false);
    }
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    if (mode === "register") void register();
    else void signIn(email, password);
  }
  async function register() {
    if (busy) return;
    if (password !== confirmPassword) {
      setError(
        "The passwords do not match. Enter the same password in both fields.",
      );
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api(
        "/auth/register",
        json({
          name: name.trim(),
          email: email.trim().toLowerCase(),
          password,
        }),
      );
      const user = await api<User>("/auth/me");
      onLogin(user);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  function changeMode(next: "login" | "register") {
    setMode(next);
    setError("");
    setPassword("");
    setConfirmPassword("");
    setShowPassword(false);
  }
  return (
    <div className="login-page">
      <section className="login-story">
        <Logo />
        <div>
          <span className="eyebrow">BUILT FOR YOUR ENTERPRISE</span>
          <h1>
            Your knowledge.
            <br />
            Within reach.
          </h1>
          <p>
            Search your business files. Find exact evidence.
            <br />
            Verify every result.
          </p>
          <div className="login-evidence">
            <span className="evidence-label">
              <FileSearch size={16} /> SOURCE-VERIFIED EVIDENCE
            </span>
            <strong>Every result has a source.</strong>
            <div>
              <FileIcon type="xlsx" />
              <span>
                Workbook <ChevronRight size={14} /> Sheet{" "}
                <ChevronRight size={14} /> Cell
              </span>
              <CheckCheck size={20} />
            </div>
          </div>
        </div>
        <span className="login-bottom">
          <ShieldCheck size={17} />
          Private Enterprise Search, Evidence Retrieval & Audit
        </span>
      </section>
      <section className="login-form-wrap">
        <form className="login-form" onSubmit={submit}>
          <span className="login-lock">
            <LockKeyhole size={24} />
          </span>
          <h2>
            {mode === "register" ? "Create your account" : "Welcome to MCCIA"}
          </h2>
          <p>
            {mode === "register"
              ? "Set up your login and a private document workspace."
              : "Sign in to your document workspace."}
          </p>
          {allowRegistration && (
            <div className="auth-mode-switch" aria-label="Account access">
              <button
                type="button"
                disabled={busy}
                aria-pressed={mode === "login"}
                onClick={() => changeMode("login")}
              >
                Sign in
              </button>
              <button
                type="button"
                disabled={busy}
                aria-pressed={mode === "register"}
                onClick={() => changeMode("register")}
              >
                Create account
              </button>
            </div>
          )}
          {error && <ErrorBox message={error} />}
          {connectionError && (
            <div role="status">
              <ErrorBox message={connectionError} />
              {backendConfigured && (
                <button
                  type="button"
                  className="button small"
                  disabled={optionsLoading}
                  onClick={() => setOptionsAttempt((attempt) => attempt + 1)}
                >
                  {optionsLoading ? "Connecting…" : "Retry connection"}
                </button>
              )}
            </div>
          )}
          {mode === "register" && (
            <label>
              Full name
              <input
                autoComplete="name"
                required
                maxLength={120}
                placeholder="Your full name"
                value={name}
                onChange={(e) => setName(e.target.value)}
              />
            </label>
          )}
          <label>
            Work email
            <input
              type="email"
              autoComplete="username"
              placeholder="you@company.com"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              onBlur={() => setEmail((value) => value.trim().toLowerCase())}
              spellCheck={false}
              autoCapitalize="none"
            />
          </label>
          <label>
            Password
            <div className="password-field">
              <input
                type={showPassword ? "text" : "password"}
                autoComplete={
                  mode === "register" ? "new-password" : "current-password"
                }
                placeholder={
                  mode === "register"
                    ? "At least 10 characters"
                    : "Enter your password"
                }
                minLength={mode === "register" ? 10 : undefined}
                maxLength={200}
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <button
                type="button"
                className="icon-button"
                aria-label={showPassword ? "Hide password" : "Show password"}
                aria-pressed={showPassword}
                onClick={() => setShowPassword((value) => !value)}
              >
                {showPassword ? <EyeOff size={18} /> : <Eye size={18} />}
              </button>
            </div>
          </label>
          {mode === "register" && (
            <label>
              Confirm password
              <input
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                required
                maxLength={200}
                placeholder="Re-enter your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </label>
          )}
          <button
            className="button primary"
            disabled={busy || !backendConfigured}
          >
            {mode === "register"
              ? busy
                ? "Creating your workspace…"
                : "Create account & continue"
              : busy
                ? "Signing in…"
                : "Sign in to workspace"}
            <ArrowRight size={18} />
          </button>
          {mode === "login" && demoAccounts.length > 0 && (
            <section
              className="demo-login"
              aria-label="Local demonstration accounts"
            >
              <h3>Try the local demo</h3>
              <p>Use a ready-to-use account to explore the workspace.</p>
              <div className="demo-account-buttons">
                {demoAccounts.map((account) => (
                  <button
                    key={account.email}
                    type="button"
                    className="button small"
                    disabled={busy}
                    onClick={() => {
                      setEmail(account.email);
                      setPassword(account.password);
                      void signIn(account.email, account.password);
                    }}
                    aria-label={`Sign in as demo ${account.role}`}
                  >
                    {account.role}
                  </button>
                ))}
              </div>
            </section>
          )}
          <div className="login-help">
            <LockKeyhole size={16} />
            <span>
              {allowRegistration
                ? "Create an account to get your own private workspace. Ask an administrator for access to an existing team workspace."
                : "Your work email needs an account in this installation. An administrator can add it in Settings → User management, then assign workspace access in Workspaces."}
            </span>
          </div>
        </form>
      </section>
    </div>
  );
}
