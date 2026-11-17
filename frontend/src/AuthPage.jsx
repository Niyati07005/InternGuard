import { useState } from "react";
import { LoaderCircle, LockKeyhole, Moon, Shield, Sun } from "lucide-react";
import { apiRequest } from "./api.js";

export default function AuthPage({ onAuthenticated, onCancel, dark, setDark }) {
  const [mode, setMode] = useState("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  const submit = async event => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const response = await apiRequest(`/auth/${mode === "register" ? "register" : "login"}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const result = await response.json();
      onAuthenticated(result.user);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  return <div className={`app-shell ${dark ? "dark" : ""} grid min-h-screen place-items-center px-4 py-10`}>
    <div className="w-full max-w-[420px]">
      <div className="mb-7 flex items-center justify-between">
        <div className="flex items-center gap-3"><div className="rounded-xl bg-blue-600 p-2.5 text-white"><Shield size={22}/></div><div><p className="text-[17px] font-bold">InternGuard</p><p className="muted text-xs">Opportunity protection</p></div></div>
        <div className="flex items-center gap-2">{onCancel&&<button className="secondary text-xs" onClick={onCancel}>Continue as guest</button>}<button className="secondary p-2" onClick={() => setDark(!dark)} aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}>{dark ? <Sun size={16}/> : <Moon size={16}/>}</button></div>
      </div>
      <section className="surface p-6 sm:p-8">
        <div className="mb-6 flex h-11 w-11 items-center justify-center rounded-xl bg-blue-50 text-blue-700"><LockKeyhole size={20}/></div>
        <h1 className="text-2xl font-semibold tracking-tight">{mode === "login" ? "Welcome back" : "Create your account"}</h1>
        <p className="muted mt-2 text-sm leading-5">{mode === "login" ? "Sign in to review and manage your private scan history." : "Create an account to keep your scans private to you."}</p>
        <form className="mt-6 space-y-4" onSubmit={submit}>
          <label className="block"><span className="mb-1.5 block text-sm font-medium">Email address</span><input className="field" type="email" autoComplete="email" value={email} onChange={event => setEmail(event.target.value)} maxLength={254} required placeholder="you@example.com"/></label>
          <label className="block"><span className="mb-1.5 block text-sm font-medium">Password</span><input className="field" type="password" autoComplete={mode === "login" ? "current-password" : "new-password"} value={password} onChange={event => setPassword(event.target.value)} minLength={mode === "register" ? 12 : 1} maxLength={128} required placeholder={mode === "register" ? "At least 12 characters" : "Your password"}/></label>
          {mode === "register" && <p className="muted text-xs">Use at least 12 characters. Passwords are hashed before they are stored.</p>}
          {error && <p role="alert" className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-800">{error}</p>}
          <button className="primary w-full" disabled={busy}>{busy ? <LoaderCircle size={16} className="animate-spin"/> : <LockKeyhole size={16}/>} {mode === "login" ? "Sign in" : "Create account"}</button>
        </form>
        <div className="muted mt-5 border-t pt-4 text-center text-sm" style={{borderColor:"var(--line)"}}>
          {mode === "login" ? "New to InternGuard? " : "Already have an account? "}
          <button className="font-semibold text-blue-600" onClick={() => { setMode(mode === "login" ? "register" : "login"); setError(""); }}> {mode === "login" ? "Create an account" : "Sign in"}</button>
        </div>
      </section>
      <p className="muted mt-5 text-center text-xs">Your scan history is accessible only after you sign in.</p>
    </div>
  </div>;
}
