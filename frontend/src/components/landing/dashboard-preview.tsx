import {
  Beaker,
  FileText,
  FlaskConical,
  FolderKanban,
  Microscope,
  Rows3,
  ShieldCheck,
  Users,
} from "lucide-react";

import { AuditLogTable } from "./audit-log-table";

/**
 * Static mock of the in-product dashboard, framed as a browser window.
 * Used as the hero visual on the landing page.
 */
export function DashboardPreview() {
  return (
    <div className="relative mx-auto max-w-[1152px]">
      <div className="overflow-hidden rounded-[12px] border border-slate-200 bg-white shadow-2xl shadow-slate-900/10">
        {/* Browser top bar */}
        <div className="flex items-center gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3">
          <div className="flex gap-1.5">
            <span className="h-3 w-3 rounded-full bg-red-400/80" />
            <span className="h-3 w-3 rounded-full bg-yellow-400/80" />
            <span className="h-3 w-3 rounded-full bg-green-400/80" />
          </div>
          <div className="mx-auto flex h-7 w-full max-w-md items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-xs text-slate-500">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
            app.labsmith.io/yamamoto-lab/microfluidics/sessions
          </div>
          <div className="w-12" />
        </div>

        {/* App body */}
        <div className="grid grid-cols-[256px_1fr]">
          {/* Sidebar */}
          <aside className="border-r border-slate-200 bg-slate-50 p-4">
            <div className="flex items-center gap-2 px-1 pb-4 text-sm font-bold text-slate-900">
              <span className="grid h-6 w-6 place-items-center rounded-md bg-slate-900 text-white">
                <FlaskConical className="h-3.5 w-3.5" />
              </span>
              LabSmith
            </div>
            <p className="px-1 pt-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
              Yamamoto Lab
            </p>
            <ul className="mt-2 space-y-1 text-sm">
              <SidebarItem icon={<FolderKanban className="h-4 w-4" />} label="Projects" />
              <SidebarItem icon={<Rows3 className="h-4 w-4" />} label="Design sessions" active />
              <SidebarItem icon={<FileText className="h-4 w-4" />} label="SOPs & protocols" />
              <SidebarItem icon={<Users className="h-4 w-4" />} label="Members" />
            </ul>
            <p className="px-1 pt-6 text-[10px] font-semibold uppercase tracking-[0.08em] text-slate-400">
              Recent sessions
            </p>
            <ul className="mt-2 space-y-1 text-sm">
              <SidebarItem icon={<Microscope className="h-4 w-4" />} label="TMA mold · 6×8" muted />
              <SidebarItem icon={<Microscope className="h-4 w-4" />} label="Pipette tip rack v3" muted />
              <SidebarItem icon={<Beaker className="h-4 w-4" />} label="Intern onboarding" muted />
            </ul>
          </aside>

          {/* Main */}
          <div className="bg-white">
            {/* Header */}
            <header className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
              <div>
                <p className="text-xs uppercase tracking-[0.08em] text-slate-400">
                  Yamamoto Lab · Microfluidics
                </p>
                <h3 className="text-lg font-bold text-slate-900">
                  Bench overview
                </h3>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700">
                  <span className="status-dot !h-1.5 !w-1.5" />
                  Printers online · 2/2
                </span>
                <span className="rounded-md border border-slate-200 px-2.5 py-1 text-xs font-medium text-slate-600">
                  SOP index · synced
                </span>
              </div>
            </header>

            {/* Stats row */}
            <div className="grid grid-cols-3 gap-4 border-b border-slate-200 px-6 py-5">
              <StatBlock label="Active design sessions" value="14" delta="+3 this wk" tone="positive" />
              <StatBlock label="Parts generated · 7d" value="47" delta="+12%" tone="positive" />
              <StatBlock label="SOPs indexed" value="26" delta="2 pending" tone="warning" />
            </div>

            {/* Audit table */}
            <div className="space-y-3 px-6 py-5">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-sm font-semibold text-slate-900">Lab activity</h4>
                  <p className="text-xs text-slate-500">
                    Recent design generations, SOP changes, and member actions
                  </p>
                </div>
                <span className="rounded-md bg-slate-50 px-2.5 py-1 font-mono text-[11px] text-slate-500">
                  live · sse
                </span>
              </div>
              <AuditLogTable />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

function SidebarItem({
  icon,
  label,
  active,
  muted,
}: {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  muted?: boolean;
}) {
  return (
    <li>
      <span
        className={[
          "flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors",
          active
            ? "bg-white font-semibold text-slate-900 shadow-sm ring-1 ring-slate-200"
            : muted
              ? "text-slate-500"
              : "text-slate-700 hover:bg-white",
        ].join(" ")}
      >
        {icon}
        {label}
      </span>
    </li>
  );
}

function StatBlock({
  label,
  value,
  delta,
  tone,
}: {
  label: string;
  value: string;
  delta: string;
  tone: "positive" | "warning";
}) {
  return (
    <div className="rounded-[12px] border border-slate-200 bg-white p-4">
      <p className="text-xs font-medium uppercase tracking-[0.06em] text-slate-500">
        {label}
      </p>
      <div className="mt-2 flex items-end justify-between">
        <p className="text-2xl font-bold text-slate-900 tabular-nums">{value}</p>
        <span
          className={[
            "rounded-full px-2 py-0.5 text-[11px] font-semibold",
            tone === "positive"
              ? "bg-emerald-100 text-emerald-700"
              : "bg-yellow-100 text-yellow-700",
          ].join(" ")}
        >
          {delta}
        </span>
      </div>
    </div>
  );
}
