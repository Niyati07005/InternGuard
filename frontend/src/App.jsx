import { useEffect, useRef, useState } from "react";
import {
  Activity, AlertTriangle, ArrowDownToLine, ArrowRight, BriefcaseBusiness,
  CheckCircle2, Clock3, ExternalLink, FileSearch,
  FileText, Globe2, LayoutDashboard, LoaderCircle, LockKeyhole, Moon, Search,
  LogOut, Shield, ShieldAlert, ShieldCheck, Sun, Trash2, Upload, X,
} from "lucide-react";
import {
  Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer,
  Tooltip, XAxis, YAxis,
} from "recharts";
import AuthPage from "./AuthPage.jsx";
import { API, apiRequest } from "./api.js";

const NAV = [
  ["Dashboard", LayoutDashboard], ["Job & Internship Analyzer", BriefcaseBusiness],
  ["Offer Letter Scanner", FileSearch], ["URL & Company Verification", Globe2],
  ["Scan History", Clock3], ["Settings", LockKeyhole],
];
const COLORS = ["#22a06b", "#e7a331", "#e15b4e"];
const PREVIEW_USER = { id: "preview", is_guest: true };
const PREVIEW_SCANS = [
  {
    scan_id: "preview-low",
    created_at: "2026-11-17T10:00:00Z",
    job_title: "Software Engineering Intern",
    company_name: "Northstar Analytics (Sample)",
    scan_type: "job",
    risk_score: 18,
    risk_category: "LOW",
    summary: "Clear role details and a standard interview process.",
    sample_data: true,
  },
  {
    scan_id: "preview-medium",
    created_at: "2026-11-12T10:00:00Z",
    job_title: "Remote Data Entry Internship",
    company_name: "BrightPath Staffing (Sample)",
    scan_type: "job",
    risk_score: 46,
    risk_category: "MEDIUM",
    summary: "A refundable registration fee is requested after selection.",
    sample_data: true,
  },
  {
    scan_id: "preview-high",
    created_at: "2026-11-05T10:00:00Z",
    job_title: "Guaranteed Remote Placement Program",
    company_name: "Summit Career Group (Sample)",
    scan_type: "job",
    risk_score: 84,
    risk_category: "HIGH",
    summary: "A guaranteed placement is paired with upfront fees and urgency.",
    sample_data: true,
  },
];
const PREVIEW_DASHBOARD = {
  total_scans: 3,
  high_risk: 1,
  medium_risk: 1,
  low_risk: 1,
  distribution: [
    { name: "Low", value: 1 },
    { name: "Medium", value: 1 },
    { name: "High", value: 1 },
  ],
  monthly_trends: [{ month: "Nov", scans: 3, high_risk: 1 }],
  scan_type_summary: [
    { name: "Job analysis", value: 3 },
    { name: "Offer letter", value: 0 },
    { name: "URL verification", value: 0 },
  ],
};

function RiskPill({ category }) {
  return <span className={`inline-flex rounded-full px-2.5 py-1 text-[11px] font-bold tracking-wide risk-${(category || "low").toLowerCase()}`}>{category || "LOW"} RISK</span>;
}

function Metric({ label, value, note, icon: Icon, tone }) {
  return <div className="surface p-5"><div className="flex items-start justify-between"><div><p className="muted text-sm">{label}</p><p className="mt-2 text-3xl font-semibold tracking-tight">{value}</p></div><div className={`rounded-xl p-2.5 ${tone}`}><Icon size={19}/></div></div><p className="muted mt-3 text-xs">{note}</p></div>;
}

function ResultPanel({ result, onOpenHistory }) {
  if (!result) return null;
  return <div className="surface mt-6 p-5 sm:p-6">
    {result.sample_data&&<p className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-xs font-medium text-blue-900">Sample demonstration scan — not a real opportunity or investigation.</p>}
    <div className="flex flex-wrap items-start justify-between gap-4 border-b pb-5" style={{borderColor:"var(--line)"}}>
      <div><p className="muted text-xs font-semibold uppercase tracking-wider">Analysis complete · Scan #{result.scan_id}</p><h2 className="mt-2 text-xl font-semibold">{result.company_name || result.domain || "Opportunity review"}</h2><p className="muted mt-1 text-sm">{result.summary}</p></div>
      <div className="flex items-center gap-3"><div className="text-right"><p className="muted text-xs">Risk score</p><p className="text-2xl font-bold">{result.risk_score}<span className="muted text-sm font-medium"> / 100</span></p></div><RiskPill category={result.risk_category}/></div>
    </div>
    {result.extracted_details && <div className="mt-5 grid gap-3 rounded-lg p-4 sm:grid-cols-3" style={{background:"var(--soft)"}}>{Object.entries({Company:result.extracted_details.company,"Job title":result.extracted_details.job_title,Salary:result.extracted_details.salary}).map(([label,value])=><div key={label}><p className="muted text-[11px] font-semibold uppercase tracking-wide">{label}</p><p className="mt-1 text-sm font-medium">{value}</p></div>)}</div>}
    <div className="mt-5 grid gap-5 md:grid-cols-2">
      <div><h3 className="mb-3 flex items-center gap-2 font-semibold"><AlertTriangle size={16} className="text-amber-600"/>Potential warning signs</h3>
        {result.red_flags?.length ? result.red_flags.map((f,i)=><div key={i} className="mb-2 rounded-lg p-3" style={{background:"var(--soft)"}}><p className="text-sm font-medium">{f.title}</p><p className="muted mt-1 text-xs leading-5">{f.explanation}</p></div>):<p className="muted rounded-lg p-3 text-sm" style={{background:"var(--soft)"}}>No configured high-signal warning phrases detected.</p>}
      </div>
      <div><h3 className="mb-3 flex items-center gap-2 font-semibold"><ShieldCheck size={16} className="text-emerald-600"/>Safety recommendations</h3>
        {(result.recommendations || []).map((r,i)=><p key={i} className="muted mb-2 flex gap-2 text-sm leading-5"><CheckCircle2 size={15} className="mt-0.5 shrink-0 text-emerald-600"/>{r}</p>)}
      </div>
      {result.verification?.length > 0 && <div className="md:col-span-2"><h3 className="mb-3 flex items-center gap-2 font-semibold"><Globe2 size={16}/>Verification findings</h3>{result.verification.map((f,i)=><p key={i} className="muted mb-2 text-sm"><b className="text-inherit">{f.title}:</b> {f.explanation}</p>)}</div>}
      {result.verification_details && <VerificationDetails details={result.verification_details}/>}
    </div>
    <p className="muted mt-5 border-t pt-4 text-xs leading-5" style={{borderColor:"var(--line)"}}>{result.disclaimer}</p>
    <div className="mt-4 flex flex-wrap gap-2"><a className="secondary text-sm no-underline" href={`${API}/scans/${result.scan_id}/report.pdf`}><ArrowDownToLine size={15}/>Download PDF report</a><button onClick={onOpenHistory} className="secondary text-sm">View scan history</button></div>
  </div>;
}

function VerificationDetails({details}) {
  const entries = [
    ["DNS records", details.dns],
    ["Domain registration", details.registration],
    ["HTTPS certificate", details.https],
    ["Threat intelligence", details.threat_intelligence],
  ].filter(([, value]) => value);
  return <div className="md:col-span-2"><h3 className="mb-3 font-semibold">External checks · status shown per source</h3><div className="grid gap-3 sm:grid-cols-2">{entries.map(([label, value])=><div key={label} className="rounded-lg p-3" style={{background:"var(--soft)"}}><div className="flex items-center justify-between gap-2"><p className="text-sm font-medium">{label}</p><span className="muted rounded-full border px-2 py-0.5 text-[10px] uppercase" style={{borderColor:"var(--line)"}}>{value.status?.replaceAll("_"," ")||"unknown"}</span></div><p className="muted mt-2 text-xs leading-5">{value.message}</p>{value.age_days!=null&&<p className="muted mt-1 text-xs">Registered {value.age_days.toLocaleString()} days ago{value.registration_date?` (${value.registration_date.slice(0,10)})`:""}.</p>}{value.registrar&&<p className="muted mt-1 text-xs">Registrar: {value.registrar}</p>}{value.records&&Object.entries(value.records).some(([, records])=>records.length>0)&&<p className="muted mt-1 break-words text-xs">Records: {Object.entries(value.records).filter(([, records])=>records.length>0).map(([type, records])=>`${type}: ${records.join(", ")}`).join(" · ")}</p>}{value.malicious!=null&&<p className="muted mt-1 text-xs">Malicious: {value.malicious} · suspicious: {value.suspicious} · harmless: {value.harmless}</p>}</div>)}</div><p className="muted mt-2 text-[11px]">An unavailable or unconfigured check is not a clean result. HTTPS and domain registration do not establish that an employer is genuine.</p></div>;
}

export default function App() {
  const [page, setPage] = useState("Dashboard");
  const [dark, setDark] = useState(localStorage.getItem("internguard-theme") === "dark");
  const [user, setUser] = useState(null);
  const [authLoading, setAuthLoading] = useState(true);
  const [showAuth, setShowAuth] = useState(false);
  const [previewMode, setPreviewMode] = useState(false);
  const [dashboard, setDashboard] = useState(null);
  const [modelEvaluation, setModelEvaluation] = useState(null);
  const [demoLoading, setDemoLoading] = useState(false);
  const [scans, setScans] = useState([]);
  const [selected, setSelected] = useState(null);
  const [notice, setNotice] = useState("");

  const refresh = async () => {
    try {
      const [d, s, m] = await Promise.all([
        apiRequest("/dashboard"), apiRequest("/scans"), apiRequest("/model/metrics"),
      ]);
      setDashboard(await d.json());
      setScans(await s.json());
      setModelEvaluation(await m.json());
    } catch (e) { setNotice(e.message); }
  };
  useEffect(() => {
    let active = true;
    apiRequest("/auth/me")
      .then(response => response.json())
      .then(async currentUser => {
        if (!active) return;
        setUser(currentUser);
        if (currentUser.is_guest) {
          const sampleKey = `internguard-sample-scans-${currentUser.id}`;
          if (!localStorage.getItem(sampleKey)) {
            await apiRequest("/demo-scans", { method: "POST" });
            localStorage.setItem(sampleKey, "loaded");
          }
        }
        await refresh();
      })
      .catch(error => {
        if (active && error.status !== 401) {
          setPreviewMode(true);
          setUser(PREVIEW_USER);
          setDashboard(PREVIEW_DASHBOARD);
          setScans(PREVIEW_SCANS);
          setModelEvaluation(null);
          setNotice("");
        }
      })
      .finally(() => { if (active) setAuthLoading(false); });
    return () => { active = false; };
  }, []);
  useEffect(() => { localStorage.setItem("internguard-theme", dark ? "dark" : "light"); }, [dark]);
  const go = name => { setPage(name); setSelected(null); setNotice(""); };
  const authenticated = async currentUser => {
    setUser(currentUser);
    setShowAuth(false);
    setPage("Dashboard");
    await refresh();
  };
  const logout = async () => {
    try {
      await apiRequest("/auth/logout", { method: "POST" });
      setScans([]);
      setDashboard(null);
      setModelEvaluation(null);
      setSelected(null);
      const response = await apiRequest("/auth/me");
      setUser(await response.json());
      setPage("Dashboard");
      await refresh();
    } catch (error) { setNotice(error.message); }
  };
  const loadDemoScans = async () => {
    setDemoLoading(true);
    setNotice("");
    try {
      await apiRequest("/demo-scans", { method: "POST" });
      await refresh();
    } catch (error) {
      setNotice(error.message);
    } finally {
      setDemoLoading(false);
    }
  };

  if (authLoading) {
    return <div className={`app-shell ${dark ? "dark" : ""} grid min-h-screen place-items-center`}>
      <LoaderCircle className="animate-spin text-blue-600" size={26}/>
    </div>;
  }
  if (!user) return <div className={`app-shell ${dark ? "dark" : ""} grid min-h-screen place-items-center px-4`}><section className="surface max-w-md p-7 text-center"><h1 className="text-xl font-semibold">InternGuard is unavailable</h1><p className="muted mt-2 text-sm">{notice || "The local API could not be reached. Start the backend and retry."}</p><button className="primary mt-5" onClick={()=>window.location.reload()}>Retry</button></section></div>;
  if (showAuth) return <AuthPage onAuthenticated={authenticated} onCancel={()=>setShowAuth(false)} dark={dark} setDark={setDark}/>;

  return <div className={`app-shell ${dark ? "dark" : ""} main-layout flex`}>
    <aside className="sidebar sticky top-0 flex h-screen w-[250px] shrink-0 flex-col px-4 py-5">
      <div className="flex items-center gap-3 px-2 pb-8"><div className="rounded-xl bg-blue-600 p-2.5 text-white"><Shield size={22}/></div><div><p className="text-[17px] font-bold tracking-tight">InternGuard</p><p className="muted text-[11px]">Opportunity protection</p></div></div>
      <p className="muted px-3 pb-2 text-[10px] font-bold uppercase tracking-[.13em]">Workspace</p>
      <nav className="flex flex-col gap-1">{NAV.map(([name,Icon])=><button key={name} onClick={()=>go(name)} className={`nav-link ${page===name?"active":""}`}><Icon size={17}/>{name}</button>)}</nav>
      <div className="sidebar-bottom mt-auto">
        <div className="mb-4 rounded-xl border p-3" style={{borderColor:"var(--line)",background:"var(--soft)"}}><div className="flex items-center gap-2 text-xs font-semibold"><LockKeyhole size={14} className="text-emerald-600"/>{previewMode?"Prototype preview":"Private by design"}</div><p className="muted mt-1.5 text-[11px] leading-4">{previewMode?"Illustrative scans are temporary and are not saved.":user.is_guest?"Guest scans are isolated to this browser session.":"Your scans are stored in your local SQLite database."}</p></div>
        <button className="nav-link" onClick={()=>setDark(!dark)}>{dark?<Sun size={17}/>:<Moon size={17}/>}<span>{dark?"Switch to light mode":"Switch to dark mode"}</span><span className={`ml-auto h-5 w-9 rounded-full p-0.5 ${dark?"bg-blue-600":"bg-slate-300"}`}><span className={`block h-4 w-4 rounded-full bg-white transition-transform ${dark?"translate-x-4":""}`}/></span></button>
        <p className="muted px-3 pt-4 text-[10px]">INTERNGUARD · LOCAL DEMO</p>
      </div>
    </aside>
    <main className="min-w-0 flex-1">
      <header className="sticky top-0 z-10 flex h-[68px] items-center justify-between border-b px-6 sm:px-9" style={{background:"var(--surface)",borderColor:"var(--line)"}}>
        <div><p className="muted text-xs">Workspace / <span style={{color:"var(--text)"}}>{page}</span></p></div>
        <div className="flex items-center gap-3"><span className={`hidden items-center gap-1.5 text-xs sm:flex ${previewMode?"text-amber-700":"text-emerald-700"}`}><span className={`h-2 w-2 rounded-full ${previewMode?"bg-amber-500":"bg-emerald-500"}`}/>{previewMode?"Preview only":"Local analysis active"}</span><span className="muted hidden max-w-48 truncate text-xs sm:block">{user.email || (previewMode?"Prototype preview":"Guest workspace")}</span>{previewMode?<span className="muted text-xs">Read-only</span>:user.is_guest?<button className="secondary text-xs" onClick={()=>setShowAuth(true)} title="Sign in or create an account">Sign in</button>:<button className="secondary p-2" onClick={logout} aria-label="Sign out" title="Sign out"><LogOut size={15}/></button>}<div className="grid h-8 w-8 place-items-center rounded-full bg-blue-50 text-xs font-semibold text-blue-700">IG</div></div>
      </header>
      <div className="mx-auto max-w-[1440px] px-5 py-7 sm:px-9">
        {notice && <div role="alert" className={`mb-5 flex items-center justify-between rounded-lg border px-4 py-3 text-sm ${previewMode?"border-blue-200 bg-blue-50 text-blue-900":"border-red-200 bg-red-50 text-red-800"}`}><span>{previewMode?notice:`${notice} — ensure the API is running.`}</span><button onClick={()=>setNotice("")}><X size={16}/></button></div>}
        {page==="Dashboard" && <DashboardPage data={dashboard} modelEvaluation={modelEvaluation} scans={scans} go={go} onLoadDemo={loadDemoScans} demoLoading={demoLoading} previewMode={previewMode}/>}
        {page==="Job & Internship Analyzer" && <AnalyzerPage refresh={refresh} setNotice={setNotice} openHistory={()=>go("Scan History")}/>}
        {page==="Offer Letter Scanner" && <OfferPage refresh={refresh} setNotice={setNotice} openHistory={()=>go("Scan History")}/>}
        {page==="URL & Company Verification" && <VerifyPage refresh={refresh} setNotice={setNotice} openHistory={()=>go("Scan History")}/>}
        {page==="Scan History" && <HistoryPage scans={scans} refresh={refresh} selected={selected} setSelected={setSelected} setNotice={setNotice}/>}
        {page==="Settings" && <SettingsPage dark={dark} setDark={setDark}/>}
      </div>
      <footer className="muted border-t px-6 py-5 text-center text-xs sm:px-9" style={{borderColor:"var(--line)"}}>Preliminary risk indicators only. Always verify an opportunity independently before taking action.</footer>
    </main>
  </div>;
}

function PageHeading({eyebrow,title,description,action}) {
  return <div className="mb-7 flex flex-wrap items-end justify-between gap-4"><div><p className="mb-2 text-[11px] font-bold uppercase tracking-[.14em] text-blue-600">{eyebrow}</p><h1 className="text-2xl font-semibold tracking-tight sm:text-[28px]">{title}</h1><p className="muted mt-2 max-w-2xl text-sm leading-6">{description}</p></div>{action}</div>;
}

function DashboardPage({data,modelEvaluation,scans,go,onLoadDemo,demoLoading,previewMode}) {
  const distribution = data?.distribution?.some(d=>d.value) ? data.distribution : [{name:"Low",value:0},{name:"Medium",value:0},{name:"High",value:0}];
  return <>
    <PageHeading eyebrow="Overview" title="Opportunity safety dashboard" description="A clear view of your recent checks and the risk signals they surfaced." action={<button className="primary" onClick={()=>go("Job & Internship Analyzer")}><BriefcaseBusiness size={16}/>Analyze opportunity</button>}/>
    <div className="mb-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <Metric label="Total scans" value={data?.total_scans??"—"} note={previewMode?"Illustrative samples · not saved":"All analyses saved locally"} icon={Activity} tone="bg-blue-50 text-blue-600"/>
      <Metric label="High risk" value={data?.high_risk??"—"} note="Score 61–100 · review carefully" icon={ShieldAlert} tone="bg-red-50 text-red-600"/>
      <Metric label="Medium risk" value={data?.medium_risk??"—"} note="Score 31–60 · verify details" icon={AlertTriangle} tone="bg-amber-50 text-amber-600"/>
      <Metric label="Low risk" value={data?.low_risk??"—"} note="Score 0–30 · not a guarantee" icon={ShieldCheck} tone="bg-emerald-50 text-emerald-600"/>
    </div>
    <div className="mb-6 grid gap-5 xl:grid-cols-[1.4fr_1fr]">
      <section className="surface p-5"><div className="mb-4 flex items-start justify-between"><div><h2 className="font-semibold">Scan activity</h2><p className="muted mt-1 text-xs">{previewMode?"Illustrative monthly sample activity":"Monthly scans and high-risk findings from your database"}</p></div><Activity size={17} className="muted"/></div>
        {data?.monthly_trends?.length ? <div className="h-[240px]"><ResponsiveContainer width="100%" height="100%"><AreaChart data={data.monthly_trends}><defs><linearGradient id="scanFill" x1="0" x2="0" y1="0" y2="1"><stop offset="0%" stopColor="#3b82f6" stopOpacity={.2}/><stop offset="95%" stopColor="#3b82f6" stopOpacity={0}/></linearGradient></defs><CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#e8edf3"/><XAxis dataKey="month" tickLine={false} axisLine={false} tick={{fontSize:11,fill:"#788497"}}/><YAxis allowDecimals={false} tickLine={false} axisLine={false} tick={{fontSize:11,fill:"#788497"}}/><Tooltip/><Area type="monotone" dataKey="scans" name="Scans" stroke="#3478e5" strokeWidth={2} fill="url(#scanFill)"/><Area type="monotone" dataKey="high_risk" name="High risk" stroke="#e15b4e" strokeWidth={2} fill="transparent"/></AreaChart></ResponsiveContainer></div>:<EmptyChart text="Your monthly scan trend will appear here after your first analysis."/>}
      </section>
      <section className="surface p-5"><div className="mb-1"><h2 className="font-semibold">Risk distribution</h2><p className="muted mt-1 text-xs">{previewMode?"Illustrative sample opportunities":"Based on all saved scan results"}</p></div>
        {data?.total_scans ? <div className="relative h-[225px]"><ResponsiveContainer width="100%" height="100%"><PieChart><Pie data={distribution} innerRadius={62} outerRadius={88} paddingAngle={4} dataKey="value">{distribution.map((d,i)=><Cell key={d.name} fill={COLORS[i]}/>)}</Pie><Tooltip/></PieChart></ResponsiveContainer><div className="pointer-events-none absolute inset-0 flex flex-col items-center justify-center"><b className="text-2xl">{data.total_scans}</b><span className="muted text-[11px]">{previewMode?"sample scans":"total scans"}</span></div></div>:<EmptyChart text="No risk data yet. Results from your own scans appear here."/>}
        <div className="flex justify-center gap-4">{distribution.map((d,i)=><span className="muted flex items-center gap-1.5 text-xs" key={d.name}><i className="h-2 w-2 rounded-full" style={{background:COLORS[i]}}/>{d.name} {d.value}</span>)}</div>
      </section>
    </div>
    <section className="surface mb-6 p-5"><div className="mb-4"><h2 className="font-semibold">Opportunity analysis summary</h2><p className="muted mt-1 text-xs">{previewMode?"Illustrative preview data · not saved":"Saved scans by type · database records only"}</p></div><div className="grid gap-3 sm:grid-cols-3">{(data?.scan_type_summary||[]).map((item,i)=><div key={item.name} className="rounded-lg p-4" style={{background:"var(--soft)"}}><p className="muted text-xs">{item.name}</p><p className="mt-1 text-2xl font-semibold">{item.value}</p></div>)}</div></section>
    <ModelEvaluation data={modelEvaluation}/>
    <section className="surface overflow-hidden"><div className="flex items-center justify-between px-5 py-4"><div><h2 className="font-semibold">Recent scan activity</h2><p className="muted mt-1 text-xs">{previewMode?"Illustrative sample opportunities":"Your latest analyzed opportunities"}</p></div><button onClick={()=>go("Scan History")} className="flex items-center gap-1 text-sm font-medium text-blue-600">View history <ArrowRight size={15}/></button></div>
      {scans.length ? <div className="overflow-x-auto"><table className="w-full text-left text-sm"><thead className="muted bg-slate-50/70 text-xs"><tr><th className="px-5 py-3 font-medium">Opportunity</th><th className="px-5 py-3 font-medium">Scan type</th><th className="px-5 py-3 font-medium">Date</th><th className="px-5 py-3 font-medium">Risk</th><th className="px-5 py-3 font-medium">Score</th></tr></thead><tbody>{scans.slice(0,5).map(s=><tr key={s.scan_id} className="table-row"><td className="px-5 py-3.5"><b>{s.job_title||"Link verification"}</b>{s.sample_data&&<span className="ml-2 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">SAMPLE</span>}<span className="muted mt-0.5 block text-xs">{s.company_name||"Company not provided"}</span></td><td className="muted px-5 py-3.5 capitalize">{s.scan_type.replace("_"," ")}</td><td className="muted px-5 py-3.5">{new Date(s.created_at).toLocaleDateString()}</td><td className="px-5 py-3.5"><RiskPill category={s.risk_category}/></td><td className="px-5 py-3.5 font-semibold">{s.risk_score}/100</td></tr>)}</tbody></table></div>:<div className="p-8 text-center"><div className="mx-auto mb-3 grid h-11 w-11 place-items-center rounded-full bg-blue-50 text-blue-600"><FileSearch size={20}/></div><p className="text-sm font-medium">No scans yet</p><p className="muted mt-1 text-xs">Analyze a job, check a URL, or review an offer letter to start.</p><button className="secondary mt-4" onClick={onLoadDemo} disabled={demoLoading}>{demoLoading?<LoaderCircle size={15} className="animate-spin"/>:<Activity size={15}/>}Load sample job scans</button><p className="muted mt-2 text-[11px]">Adds three illustrative scans—one per risk level—to this workspace.</p></div>}</section>
    <p className="muted mt-4 text-[11px]">{previewMode?"Preview only: sample values are illustrative and model metrics are not loaded.":"Charts and scan counts reflect your saved database records. Model performance is measured on the labeled dataset shown above."}</p>
  </>;
}

function ModelEvaluation({data}) {
  const matrix = data?.confusion_matrix?.rows || [];
  return <section className="surface mb-6 p-5"><div className="mb-4 flex flex-wrap items-start justify-between gap-3"><div><h2 className="font-semibold">Model evaluation</h2><p className="muted mt-1 text-xs">Measured on a held-out test split · fraudulent is the positive class</p></div>{data?.source_url&&<a className="text-xs font-medium text-blue-600" href={data.source_url} target="_blank" rel="noreferrer">Dataset source</a>}</div>
    {!data ? <p className="muted text-sm">Evaluation metrics are unavailable until the model is loaded.</p> : <>
      {data.baseline&&<p className="mb-4 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">Synthetic baseline is active because the licensed dataset file was not found. These holdout metrics are not representative.</p>}
      <p className="muted mb-4 text-xs">{data.source} · {data.license} · {data.records.toLocaleString()} records · {data.split} · test set: {data.test_records.toLocaleString()}</p>
      <div className="grid gap-5 lg:grid-cols-[1fr_1.2fr]">
        <div className="grid grid-cols-3 gap-3">{[["Precision",data.metrics.precision],["Recall",data.metrics.recall],["F1-score",data.metrics.f1]].map(([label,value])=><div key={label} className="rounded-lg p-4" style={{background:"var(--soft)"}}><p className="muted text-xs">{label}</p><p className="mt-1 text-xl font-semibold">{(value*100).toFixed(1)}%</p></div>)}</div>
        <div className="overflow-x-auto"><table className="w-full min-w-[330px] text-center text-xs"><caption className="muted mb-2 text-left">Confusion matrix · actual rows × predicted columns</caption><thead><tr><th className="muted p-2"></th><th className="p-2">Predicted legitimate</th><th className="p-2">Predicted fraudulent</th></tr></thead><tbody>{matrix.map((row,index)=><tr key={index} className="table-row"><th className="p-2 text-left">{index===0?"Actual legitimate":"Actual fraudulent"}</th>{row.map((count,column)=><td key={column} className="p-2 font-semibold">{count.toLocaleString()}</td>)}</tr>)}</tbody></table></div>
      </div>
      <p className="muted mt-4 text-xs leading-5">{data.evaluation_note}</p>
    </>}
  </section>;
}

function EmptyChart({text}) { return <div className="flex h-[225px] flex-col items-center justify-center text-center"><div className="mb-3 grid h-10 w-10 place-items-center rounded-full" style={{background:"var(--soft)"}}><Activity size={17} className="muted"/></div><p className="muted max-w-[230px] text-xs leading-5">{text}</p></div>; }

function AnalyzerPage({refresh,setNotice,openHistory}) {
  const [form,setForm]=useState({job_title:"",company_name:"",job_description:"",recruitment_message:"",application_url:""});
  const [result,setResult]=useState(null); const [busy,setBusy]=useState(false);
  const change=e=>setForm({...form,[e.target.name]:e.target.value});
  const submit=async e=>{e.preventDefault();setBusy(true);setNotice("");setResult(null);try{const r=await apiRequest("/analyze",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)});setResult(await r.json());await refresh();}catch(err){setNotice(err.message);}finally{setBusy(false);}};
  return <><PageHeading eyebrow="Job & internship analyzer" title="Review an opportunity" description="Check the role details and recruitment message for common warning signs before you share information or commit."/>
    <form onSubmit={submit} className="surface p-5 sm:p-7"><div className="grid gap-5 md:grid-cols-2">
      <Field label="Job or internship title" required><input className="field" name="job_title" value={form.job_title} onChange={change} placeholder="e.g. Software Engineering Intern" minLength={2} maxLength={200} required/></Field>
      <Field label="Company name"><input className="field" name="company_name" value={form.company_name} onChange={change} placeholder="e.g. Northstar Labs" maxLength={200}/></Field>
      <Field label="Job description" hint="Include responsibilities, pay, and application details where available." wide><textarea className="field min-h-36 resize-y" name="job_description" value={form.job_description} onChange={change} placeholder="Paste the job or internship description here…" minLength={20} maxLength={30000} required/></Field>
      <Field label="Recruitment message" hint="Optional: paste the email, text, or direct message you received." wide><textarea className="field min-h-28 resize-y" name="recruitment_message" value={form.recruitment_message} onChange={change} placeholder="Paste any message from the recruiter…" maxLength={10000}/></Field>
      <Field label="Application URL" hint="Optional; checked for structure only." wide><input className="field" type="url" name="application_url" value={form.application_url} onChange={change} placeholder="https://careers.example.com/role"/></Field>
    </div><div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t pt-5" style={{borderColor:"var(--line)"}}><p className="muted flex items-center gap-2 text-xs"><ShieldCheck size={15} className="text-emerald-600"/>Text is analyzed locally; never send passwords or one-time codes.</p><button className="primary" disabled={busy}>{busy?<LoaderCircle className="animate-spin" size={16}/>:<FileSearch size={16}/>}Analyze opportunity</button></div></form>
    <ResultPanel result={result} onOpenHistory={openHistory}/><p className="muted mt-4 text-xs">Risk score combines transparent rule-based checks with a TF-IDF logistic regression classifier. It is not a probability that fraud occurred.</p>
  </>;
}

function Field({label,hint,required,wide,children}) { return <label className={`block ${wide?"md:col-span-2":""}`}><span className="mb-1.5 block text-sm font-medium">{label}{required&&<span className="ml-1 text-red-500">*</span>}</span>{children}{hint&&<span className="muted mt-1.5 block text-xs">{hint}</span>}</label>; }

function OfferPage({refresh,setNotice,openHistory}) {
  const [file,setFile]=useState(null);const [result,setResult]=useState(null);const [busy,setBusy]=useState(false);
  const submit=async e=>{e.preventDefault();if(!file)return;setBusy(true);setNotice("");setResult(null);try{const body=new FormData();body.append("file",file);const r=await apiRequest("/offer-letter",{method:"POST",body});setResult(await r.json());await refresh();}catch(err){setNotice(err.message);}finally{setBusy(false);}};
  return <><PageHeading eyebrow="Offer letter scanner" title="Review an offer letter" description="Extract readable text from a PDF and check it for payment demands, suspicious claims, and missing details."/>
    <form onSubmit={submit} className="surface p-5 sm:p-7"><label htmlFor="offer-file" className="flex min-h-52 cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed p-6 text-center transition hover:border-blue-400" style={{borderColor:"var(--line)",background:"var(--soft)"}}><div className="mb-3 grid h-12 w-12 place-items-center rounded-xl bg-blue-100 text-blue-700"><Upload size={21}/></div><span className="font-semibold">{file?file.name:"Choose a PDF offer letter"}</span><span className="muted mt-2 text-xs">PDF · up to 10 MB · max 100 pages</span><input id="offer-file" type="file" accept="application/pdf,.pdf" className="sr-only" onChange={e=>setFile(e.target.files[0]||null)}/></label>
      <div className="mt-5 flex flex-wrap items-center justify-between gap-4"><p className="muted flex items-center gap-2 text-xs"><LockKeyhole size={14}/>File is processed locally and not sent to an external service.</p><button className="primary" disabled={!file||busy}>{busy?<LoaderCircle size={16} className="animate-spin"/>:<FileSearch size={16}/>}Scan offer letter</button></div>
      <p className="muted mt-4 text-xs">Selectable text is extracted directly; pages without enough text are processed with local OCR when available.</p>
    </form><ResultPanel result={result} onOpenHistory={openHistory}/></>;
}

function VerifyPage({refresh,setNotice,openHistory}) {
  const [form,setForm]=useState({url:"",company_name:"",contact_email:""});const [result,setResult]=useState(null);const [busy,setBusy]=useState(false);
  const submit=async e=>{e.preventDefault();setBusy(true);setNotice("");setResult(null);try{const r=await apiRequest("/verify",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(form)});setResult(await r.json());await refresh();}catch(err){setNotice(err.message);}finally{setBusy(false);}};
  const change=e=>setForm({...form,[e.target.name]:e.target.value});
  return <><PageHeading eyebrow="URL & company verification" title="Inspect a recruitment link" description="Check URL structure, DNS records, domain registration where available, TLS certificates, and optional VirusTotal reputation."/>
    <div className="mb-5 flex gap-3 rounded-xl border border-blue-100 bg-blue-50 p-4 text-sm text-blue-900"><Shield size={18} className="mt-0.5 shrink-0"/><p className="leading-5">Checks use bounded DNS, RDAP, and standard-port TLS requests without opening or following the submitted link. External findings are distinguished from unavailable checks. HTTPS does not authenticate a company or offer.</p></div>
    <form onSubmit={submit} className="surface p-5 sm:p-7"><div className="grid gap-5 md:grid-cols-2">
      <Field label="Application or company URL" required wide><input className="field" name="url" value={form.url} onChange={change} placeholder="https://company.example/careers" maxLength={2000} required/></Field>
      <Field label="Company name"><input className="field" name="company_name" value={form.company_name} onChange={change} placeholder="e.g. Northstar Labs"/></Field>
      <Field label="Recruiter email"><input className="field" type="email" name="contact_email" value={form.contact_email} onChange={change} placeholder="recruiter@company.example"/></Field>
    </div><div className="mt-6 flex justify-end border-t pt-5" style={{borderColor:"var(--line)"}}><button className="primary" disabled={busy}>{busy?<LoaderCircle size={16} className="animate-spin"/>:<Globe2 size={16}/>}Check URL</button></div></form>
    {result&&<div className="surface mt-6 p-5"><div className="flex flex-wrap items-center justify-between gap-3"><div><p className="muted text-xs">Detected domain</p><p className="mt-1 text-lg font-semibold">{result.domain||"Could not identify domain"}</p></div><div className="flex items-center gap-3"><span className="muted text-sm">{result.https?"HTTPS":"Not HTTPS"}</span><RiskPill category={result.risk_category}/></div></div></div>}
    <ResultPanel result={result} onOpenHistory={openHistory}/>
  </>;
}

function HistoryPage({scans,refresh,selected,setSelected,setNotice}) {
  const [search,setSearch]=useState("");const [category,setCategory]=useState("");const [type,setType]=useState("");const [busy,setBusy]=useState(false);
  const reportRef=useRef(null);
  const load=async()=>{setBusy(true);try{const q=new URLSearchParams();if(search)q.set("search",search);if(category)q.set("category",category);if(type)q.set("scan_type",type);const r=await apiRequest(`/scans?${q}`);setFiltered(await r.json());}catch(e){setNotice(e.message);}finally{setBusy(false);}};
  const [filtered,setFiltered]=useState(scans);useEffect(()=>{setFiltered(scans);},[scans]);
  useEffect(()=>{const t=setTimeout(load,180);return()=>clearTimeout(t);},[search,category,type]);
  useEffect(()=>{if(selected)reportRef.current?.scrollIntoView({behavior:"smooth",block:"start"});},[selected]);
  const remove=async id=>{if(!confirm(`Delete scan #${id}? This cannot be undone.`))return;try{await apiRequest(`/scans/${id}`,{method:"DELETE"});setSelected(null);await refresh();}catch(e){setNotice(e.message);}};
  const view=async id=>{try{const r=await apiRequest(`/scans/${id}`);setSelected(await r.json());}catch(e){setNotice(e.message);}};
  return <><PageHeading eyebrow="Scan history" title="Your saved scans" description="Search and filter your locally stored checks, open a detailed result, or export the records." action={<a href={`${API}/scans.csv`} className="secondary text-sm no-underline"><ArrowDownToLine size={15}/>Export CSV</a>}/>
    <div className="surface mb-5 flex flex-wrap gap-3 p-4"><div className="relative min-w-[220px] flex-1"><Search size={16} className="muted absolute left-3 top-1/2 -translate-y-1/2"/><input className="field pl-9" value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search company, title, summary"/></div><select className="field w-auto min-w-36" value={category} onChange={e=>setCategory(e.target.value)}><option value="">All risk levels</option><option>LOW</option><option>MEDIUM</option><option>HIGH</option></select><select className="field w-auto min-w-40" value={type} onChange={e=>setType(e.target.value)}><option value="">All scan types</option><option value="job">Job analysis</option><option value="offer_letter">Offer letter</option><option value="url">URL verification</option></select></div>
    {selected&&<div ref={reportRef} id="selected-scan-report" tabIndex={-1} className="surface mb-5 scroll-mt-24 p-5"><div className="mb-4 flex items-start justify-between"><div><p className="muted text-xs">Scan #{selected.scan_id} · {new Date(selected.created_at).toLocaleString()}</p><h2 className="mt-1 text-lg font-semibold">{selected.job_title||selected.domain||"Scan report"}</h2></div><button className="secondary p-2" onClick={()=>setSelected(null)} aria-label="Close report"><X size={16}/></button></div><ResultPanel result={selected} onOpenHistory={()=>{}}/></div>}
    <section className="surface overflow-hidden"><div className="overflow-x-auto"><table className="w-full min-w-[980px] text-left text-sm"><thead className="muted bg-slate-50/70 text-xs"><tr><th className="px-5 py-3 font-medium">Opportunity</th><th className="px-5 py-3 font-medium">Type</th><th className="px-5 py-3 font-medium">Scanned</th><th className="px-5 py-3 font-medium">Risk level</th><th className="px-5 py-3 font-medium">Score</th><th className="w-[360px] px-5 py-3 font-medium">Why this rating?</th><th className="px-5 py-3 font-medium">Actions</th></tr></thead><tbody>{filtered.map(s=><tr key={s.scan_id} className="table-row"><td className="px-5 py-3"><button className="text-left font-medium hover:text-blue-600" onClick={()=>view(s.scan_id)} title="Open scan report" aria-label={`Open report for ${s.job_title||"scan"}`}>{s.job_title||"Link verification"}</button>{s.sample_data&&<span className="ml-2 rounded-full bg-blue-50 px-2 py-0.5 text-[10px] font-semibold text-blue-700">SAMPLE</span>}<span className="muted mt-0.5 block text-xs">{s.company_name||"Company not provided"}</span></td><td className="muted px-5 py-3 capitalize">{s.scan_type.replace("_"," ")}</td><td className="muted px-5 py-3">{new Date(s.created_at).toLocaleDateString()}</td><td className="px-5 py-3"><RiskPill category={s.risk_category}/></td><td className="px-5 py-3 font-semibold">{s.risk_score}</td><td className="muted px-5 py-3 text-xs leading-5"><ul className="list-disc space-y-1 pl-4">{(s.risk_explanation||[s.summary||"No explanation was saved for this scan."]).slice(0,2).map((reason,i)=><li key={i}>{reason}</li>)}</ul>{(s.risk_explanation||[]).length>2&&<button className="mt-1 font-medium text-blue-700 hover:underline" onClick={()=>view(s.scan_id)}>View all {(s.risk_explanation||[]).length} findings</button>}</td><td className="px-5 py-3"><div className="flex gap-2"><button onClick={()=>view(s.scan_id)} className="secondary p-2" aria-label="Open scan report" title="Open scan report"><FileText size={15}/></button><a href={`${API}/scans/${s.scan_id}/report.pdf?inline=true`} target="_blank" rel="noopener noreferrer" className="secondary p-2" aria-label="Open PDF report in new tab" title="Open PDF report in new tab"><ExternalLink size={15}/></a><a href={`${API}/scans/${s.scan_id}/report.pdf`} className="secondary p-2" aria-label="Download PDF report" title="Download PDF report"><ArrowDownToLine size={15}/></a><button onClick={()=>remove(s.scan_id)} className="secondary p-2 text-red-600" aria-label="Delete scan" title="Delete scan"><Trash2 size={15}/></button></div></td></tr>)}</tbody></table>
      {busy&&<p className="muted py-5 text-center text-sm">Filtering scans…</p>}{!busy&&filtered.length===0&&<div className="p-9 text-center"><p className="font-medium">No scans found</p><p className="muted mt-1 text-sm">Try changing the filters or analyze an opportunity.</p></div>}</div></section>
  </>;
}

function SettingsPage({dark,setDark}) {
  return <><PageHeading eyebrow="Settings" title="Preferences & transparency" description="Control how InternGuard looks and understand how your scan data is handled."/>
    <div className="grid max-w-3xl gap-5">
      <section className="surface p-5"><div className="flex items-start justify-between gap-4"><div><h2 className="font-semibold">Appearance</h2><p className="muted mt-1 text-sm">Choose the display mode for this browser.</p></div><button className="secondary" onClick={()=>setDark(!dark)}>{dark?<Sun size={16}/>:<Moon size={16}/>}Switch to {dark?"light":"dark"} mode</button></div></section>
      <section className="surface p-5"><h2 className="font-semibold">Data & privacy</h2><div className="muted mt-3 space-y-3 text-sm leading-6"><p>Scan records are stored in a SQLite database on the machine running the backend and scoped to your account. Uploaded PDFs are processed by the backend; extracted text and analysis details are retained in your scan history.</p><p>URL checks make bounded DNS, RDAP and TLS requests to public infrastructure. VirusTotal is queried only when an API key is configured; user-provided links are never opened or followed. Those checks send the domain name to the relevant service.</p></div></section>
      <section className="surface p-5"><h2 className="font-semibold">Risk score & model</h2><div className="muted mt-3 space-y-3 text-sm leading-6"><p>Risk levels are LOW (0–30), MEDIUM (31–60), and HIGH (61–100). The score combines configured warning rules with a TF-IDF logistic regression classifier.</p><p>The dashboard displays measured precision, recall, F1-score, and a confusion matrix from a fixed stratified holdout split. The model's dataset, license, split, and limitation note are shown alongside the metrics; these results are not external validation.</p><p>Risk levels do not establish fraud or authenticity. Confirm employers and offers through independently sourced official channels.</p></div></section>
    </div>
  </>;
}
