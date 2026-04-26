import { UserButton } from "@clerk/nextjs";
import { FlaskConical } from "lucide-react";
import { Suspense } from "react";
import { HierarchySidebar } from "@/components/dashboard/hierarchy-sidebar";
import { Separator } from "@/components/ui/separator";

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <div className="flex h-full min-h-screen">
      {/* Sidebar */}
      <aside className="hidden w-64 shrink-0 overflow-y-auto border-r bg-muted/30 md:block">
        <div className="flex h-14 items-center gap-2 px-4 font-semibold">
          <FlaskConical className="h-5 w-5" />
          <span>LabSmith</span>
        </div>
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
        <header className="flex h-14 items-center justify-between border-b px-6">
          <div className="flex items-center gap-2 md:hidden">
            <FlaskConical className="h-5 w-5" />
            <span className="font-semibold">LabSmith</span>
          </div>
          <div className="ml-auto">
            <UserButton />
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6">{children}</main>
      </div>
    </div>
  );
}
