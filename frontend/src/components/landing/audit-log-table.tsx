type Status = "success" | "warning" | "failed";

interface Row {
  user: string;
  action: string;
  resource: string;
  status: Status;
  time: string;
}

const ROWS: Row[] = [
  { user: "anika.r", action: "part.generate.stl",      resource: "tma-mold · 6×8 wells, 4 mm depth", status: "success", time: "12s ago" },
  { user: "j.huang", action: "session.onboarding.open", resource: "intern onboarding · spring cohort",  status: "success", time: "1m ago" },
  { user: "system",  action: "doc.embedding.refresh",   resource: "centrifuge-sop.md (re-indexed)",      status: "warning", time: "4m ago" },
  { user: "kenji.y", action: "artifact.export.step",    resource: "pipette-tip-rack v3 · 96 positions",  status: "success", time: "11m ago" },
  { user: "anika.r", action: "validation.rule.check",   resource: "well wall < 1 mm — flagged",         status: "failed",  time: "22m ago" },
  { user: "lin.t",   action: "lab.member.invite",       resource: "rotation student · viewer role",      status: "success", time: "38m ago" },
];

const STATUS_CLASSES: Record<Status, string> = {
  success: "bg-green-100 text-green-800",
  warning: "bg-yellow-100 text-yellow-800",
  failed: "bg-red-100 text-red-800",
};

export function AuditLogTable() {
  return (
    <div className="overflow-hidden rounded-[12px] border border-slate-200">
      <div className="max-h-[320px] overflow-auto">
        <table className="w-full text-sm">
          <thead className="sticky top-0 z-10 bg-slate-50 text-xs uppercase tracking-[0.04em] text-slate-500">
            <tr>
              <th className="px-4 py-2.5 text-left font-medium">Member</th>
              <th className="px-4 py-2.5 text-left font-medium">Event</th>
              <th className="px-4 py-2.5 text-left font-medium">Detail</th>
              <th className="px-4 py-2.5 text-left font-medium">Status</th>
              <th className="px-4 py-2.5 text-right font-medium">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {ROWS.map((row, i) => (
              <tr
                key={i}
                className="bg-white transition-colors duration-200 hover:bg-[#eff6ff]"
              >
                <td className="px-4 py-3 font-medium text-slate-900">{row.user}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-600">{row.action}</td>
                <td className="px-4 py-3 font-mono text-xs text-slate-500">{row.resource}</td>
                <td className="px-4 py-3">
                  <span
                    className={[
                      "inline-flex rounded-full px-2 py-0.5 text-[11px] font-semibold",
                      STATUS_CLASSES[row.status],
                    ].join(" ")}
                  >
                    {row.status}
                  </span>
                </td>
                <td className="px-4 py-3 text-right text-slate-400">{row.time}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
