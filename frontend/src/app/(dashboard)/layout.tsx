import { UserButton } from "@clerk/nextjs";
import { FlaskConical } from "lucide-react";
import Link from "next/link";
import { Suspense } from "react";
import { HierarchySidebar } from "@/components/dashboard/hierarchy-sidebar";
import { Separator } from "@/components/ui/separator";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full min-h-screen bg-white">
      {/* Sidebar */}
      <aside className="hidden w-64 shrink-0 overflow-y-auto border-r border-slate-200 bg-slate-50 md:block">
        <Link
          href="/"
          aria-label="LabSmith home"
          className="flex h-16 items-center gap-2.5 px-5 text-[15px] font-bold tracking-tight text-slate-900 transition-colors hover:text-slate-700"
        >
          <span className="grid h-7 w-7 place-items-center rounded-md bg-[#020617] text-white">
            <FlaskConical className="h-3.5 w-3.5" />
          </span>
          <span>LabSmith</span>
        </Link>
        <Separator />
        <Suspense
          fallback={<p className="p-3 text-xs text-muted-foreground">Loading...</p>}
        >
          <HierarchySidebar />
        </Suspense>
      </aside>

      {/* Main content */}
      <div className="flex flex-1 flex-col">
        {/* Topbar */}
        <header className="flex h-16 items-center justify-between border-b border-slate-200 px-6">
          <Link
            href="/"
            aria-label="LabSmith home"
            className="flex items-center gap-2.5 transition-colors hover:text-slate-700 md:hidden"
          >
            <span className="grid h-7 w-7 place-items-center rounded-md bg-[#020617] text-white">
              <FlaskConical className="h-3.5 w-3.5" />
            </span>
            <span className="text-[15px] font-bold tracking-tight">LabSmith</span>
          </Link>
          <div className="ml-auto flex items-center gap-3">
            <span className="hidden items-center gap-1.5 rounded-full border border-emerald-200 bg-emerald-50 px-2.5 py-1 text-xs font-medium text-emerald-700 sm:inline-flex">
              <span className="status-dot !h-1.5 !w-1.5" />
              All systems operational
            </span>
            <UserButton />
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
