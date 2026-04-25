import Link from "next/link";
import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

export default async function LandingPage() {
  const { userId } = await auth();
  if (userId) {
    redirect("/dashboard/labs");
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-8 px-4">
      <div className="text-center">
        <h1 className="text-4xl font-bold tracking-tight">LabSmith</h1>
        <p className="mt-3 text-lg text-muted-foreground">
          Design lab hardware with AI. Describe what you need, get fabrication-ready files.
        </p>
      </div>
      <div className="flex gap-4">
        <Link
          href="/sign-in"
          className="inline-flex h-10 items-center justify-center rounded-md bg-primary px-6 text-sm font-medium text-primary-foreground transition-colors hover:bg-primary/90"
        >
          Sign In
        </Link>
        <Link
          href="/sign-up"
          className="inline-flex h-10 items-center justify-center rounded-md border border-input px-6 text-sm font-medium transition-colors hover:bg-accent hover:text-accent-foreground"
        >
          Sign Up
        </Link>
      </div>
    </div>
  );
}
