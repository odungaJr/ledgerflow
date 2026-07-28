"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, getAuthStatus, login, register } from "@/lib/api";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register" | "loading">("loading");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAuthStatus()
      .then((res) => setMode(res.initialized ? "login" : "register"))
      .catch(() => setMode("login"));
  }, []);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (mode === "register") {
        await register(username, password);
      } else {
        await login(username, password);
      }
      router.replace("/");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Something went wrong");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="page">
      <div className="container" style={{ maxWidth: "400px", marginTop: "3rem" }}>
        <div className="card">
          <h1 style={{ marginTop: 0 }}>{mode === "register" ? "Create your account" : "Log in"}</h1>
          {mode === "register" && (
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
              No account exists yet — set a username and password to secure LedgerFlow.
            </p>
          )}
          {mode === "loading" ? (
            <p>Loading…</p>
          ) : (
            <form className="form" onSubmit={handleSubmit}>
              <div className="formRow">
                <label htmlFor="login-username">Username</label>
                <input
                  id="login-username"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  autoComplete="username"
                  required
                />
              </div>
              <div className="formRow">
                <label htmlFor="login-password">Password</label>
                <input
                  id="login-password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  autoComplete={mode === "register" ? "new-password" : "current-password"}
                  minLength={mode === "register" ? 8 : undefined}
                  required
                />
              </div>
              {error && <div className="alert error">{error}</div>}
              <button className="btn" type="submit" disabled={submitting} style={{ width: "100%" }}>
                {submitting ? "Please wait…" : mode === "register" ? "Create account" : "Log in"}
              </button>
            </form>
          )}
        </div>
      </div>
    </main>
  );
}
