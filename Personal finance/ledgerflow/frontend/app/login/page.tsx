"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ApiError, getAuthStatus, login, register } from "@/lib/api";
import LogoMark from "@/components/LogoMark";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register" | "loading">("loading");
  const [wasEmpty, setWasEmpty] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAuthStatus()
      .then((res) => {
        setMode(res.initialized ? "login" : "register");
        setWasEmpty(!res.initialized);
      })
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
          <div style={{ display: "flex", justifyContent: "center", marginBottom: "1rem" }}>
            <LogoMark />
          </div>
          <h1 style={{ marginTop: 0, textAlign: "center" }}>
            {mode === "register" ? "Create your account" : "Log in"}
          </h1>
          {mode === "register" && (
            <p style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>
              {wasEmpty
                ? "No account exists yet — set a username and password to secure LedgerFlow."
                : "Set a username and password — your data stays private to your own account."}
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
          {mode !== "loading" && (
            <p style={{ textAlign: "center", fontSize: "0.85rem", marginTop: "1rem" }}>
              {mode === "register" ? (
                <>
                  Already have an account?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setError(null);
                      setMode("login");
                    }}
                    style={{ background: "none", border: "none", color: "var(--primary)", cursor: "pointer", padding: 0, font: "inherit" }}
                  >
                    Log in
                  </button>
                </>
              ) : (
                <>
                  New here?{" "}
                  <button
                    type="button"
                    onClick={() => {
                      setError(null);
                      setMode("register");
                    }}
                    style={{ background: "none", border: "none", color: "var(--primary)", cursor: "pointer", padding: 0, font: "inherit" }}
                  >
                    Create an account
                  </button>
                </>
              )}
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
