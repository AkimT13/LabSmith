import { UserButton } from "@clerk/nextjs";
import { auth } from "@clerk/nextjs/server";
import {
  ArrowRight,
  Beaker,
  CheckCircle2,
  Cpu,
  FileText,
  FlaskConical,
  KeyRound,
  Layers,
  LayoutDashboard,
  PlayCircle,
  ShieldCheck,
  Sparkles,
  Users,
  Workflow,
} from "lucide-react";
import Link from "next/link";

import { DashboardPreview } from "@/components/landing/dashboard-preview";
import { Faq } from "@/components/landing/faq";
import { KpiCounter } from "@/components/landing/kpi-counter";
import { PolicyToggle } from "@/components/landing/policy-toggle";

export default async function LandingPage() {
  const { userId } = await auth();
  const isSignedIn = Boolean(userId);

  return (
    <div className="flex min-h-screen flex-col bg-white text-slate-900">
      <LandingNav isSignedIn={isSignedIn} />
      <main className="flex-1">
        <Hero isSignedIn={isSignedIn} />
        <SocialProof />
        <Modules />
        <Stats />
        <Security />
        <FaqSection />
        <Cta isSignedIn={isSignedIn} />
      </main>
      <Footer />
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Navigation                                                                 */
/* -------------------------------------------------------------------------- */

function LandingNav({ isSignedIn }: { isSignedIn: boolean }) {
  return (
    <header className="glass-panel fixed inset-x-0 top-0 z-50 h-16">
      <div className="mx-auto flex h-full max-w-[1280px] items-center justify-between px-6">
        <Link href="/" className="flex items-center gap-2.5">
          <span className="grid h-7 w-7 place-items-center rounded-md bg-[#020617] text-white">
            <FlaskConical className="h-3.5 w-3.5" />
          </span>
          <span className="text-[15px] font-bold tracking-tight">LabSmith</span>
        </Link>

        <nav className="hidden items-center gap-8 md:flex">
          <a href="#platform" className="text-sm font-medium text-slate-600 hover:text-slate-900">
            Platform
          </a>
          <a href="#solutions" className="text-sm font-medium text-slate-600 hover:text-slate-900">
            Solutions
          </a>
          <a href="#security" className="text-sm font-medium text-slate-600 hover:text-slate-900">
            Security
          </a>
          <a href="#faq" className="text-sm font-medium text-slate-600 hover:text-slate-900">
            FAQ
          </a>
        </nav>

        <div className="flex items-center gap-3">
          {isSignedIn ? (
            <>
              <Link
                href="/dashboard/labs"
                className="inline-flex h-9 items-center gap-2 rounded-[8px] bg-slate-900 px-4 text-sm font-semibold text-white transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] hover:bg-slate-800"
              >
                <LayoutDashboard className="h-4 w-4" />
                Open dashboard
              </Link>
              <UserButton
                appearance={{ elements: { avatarBox: "h-8 w-8" } }}
              />
            </>
          ) : (
            <>
              <Link
                href="/sign-in"
                className="hidden text-sm font-medium text-slate-600 hover:text-slate-900 sm:inline-flex"
              >
                Sign in
              </Link>
              <Link
                href="/sign-up"
                className="inline-flex h-9 items-center rounded-[8px] bg-slate-900 px-4 text-sm font-semibold text-white transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] hover:bg-slate-800"
              >
                Book Demo
              </Link>
            </>
          )}
        </div>
      </div>
    </header>
  );
}

/* -------------------------------------------------------------------------- */
/* Hero                                                                       */
/* -------------------------------------------------------------------------- */

function Hero({ isSignedIn }: { isSignedIn: boolean }) {
  return (
    <section className="relative overflow-hidden pt-32">
      <div className="grid-bg pointer-events-none absolute inset-0" />
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[640px] bg-gradient-to-b from-white via-white/60 to-transparent" />

      <div className="relative mx-auto max-w-[1280px] px-6 pt-20 pb-24">
        <div className="mx-auto max-w-3xl text-center fade-in-up">
          <span className="inline-flex items-center gap-2 rounded-full border border-blue-100 bg-[#eff6ff] px-3.5 py-1.5 text-xs font-medium text-blue-700">
            <span className="status-dot" />
            Now in private beta · M1–M9 shipped
          </span>
          <h1 className="mt-6 text-[56px] font-extrabold leading-[1.05] tracking-[-0.03em] text-slate-900 md:text-[72px]">
            The operating system for
            <br />
            <span className="text-slate-500">modern wet labs.</span>
          </h1>
          <p className="mx-auto mt-6 max-w-2xl text-lg leading-[1.625] text-slate-600">
            Describe a part in plain English, get a fabrication-ready file. Onboard new
            members against your real SOPs. Audit every action with role-scoped access
            built for institutional review.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Link
              href={isSignedIn ? "/dashboard/labs" : "/sign-up"}
              className="group inline-flex h-11 items-center gap-2 rounded-[8px] bg-[#2563eb] px-6 text-sm font-semibold text-white shadow-sm transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] hover:bg-[#1d4ed8] hover:shadow-md"
            >
              {isSignedIn ? "Go to your dashboard" : "Start building"}
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </Link>
            <a
              href="#preview"
              className="inline-flex h-11 items-center gap-2 rounded-[8px] border border-slate-200 bg-white px-6 text-sm font-semibold text-slate-700 transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] hover:border-slate-300 hover:bg-slate-50"
            >
              <PlayCircle className="h-4 w-4 text-slate-500" />
              Watch the 90-second tour
            </a>
          </div>

          <p className="mt-5 text-xs text-slate-400">
            {isSignedIn
              ? "Welcome back · Pick up where you left off"
              : "No credit card required · SOC 2-track infrastructure · Bring your own LLM"}
          </p>
        </div>

        {/* Dashboard preview */}
        <div id="preview" className="mt-20 fade-in-up">
          <DashboardPreview />
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Social proof                                                               */
/* -------------------------------------------------------------------------- */

const LOGOS = [
  "Stanford BIO-X",
  "MIT Media Lab",
  "UCSF QBI",
  "Oxford DPAG",
  "Allen Institute",
  "ETH Zürich",
];

function SocialProof() {
  return (
    <section className="border-y border-slate-200 bg-slate-50 py-12">
      <div className="mx-auto max-w-[1280px] px-6">
        <p className="text-center text-xs font-semibold uppercase tracking-[0.16em] text-slate-500">
          Trusted by research teams at
        </p>
        <div className="mt-6 flex flex-wrap items-center justify-center gap-x-12 gap-y-4 text-slate-400">
          {LOGOS.map((logo) => (
            <span
              key={logo}
              className="text-sm font-semibold tracking-tight transition-colors hover:text-slate-700"
            >
              {logo}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Modules                                                                    */
/* -------------------------------------------------------------------------- */

const MODULES = [
  {
    icon: <Sparkles className="h-5 w-5" />,
    tint: "bg-blue-50 text-blue-600",
    title: "Conversational CAD",
    body: "Describe wells, racks, or molds in plain English. The agent extracts a typed spec and produces an STL/STEP you can ship to a printer.",
  },
  {
    icon: <Users className="h-5 w-5" />,
    tint: "bg-emerald-50 text-emerald-600",
    title: "Onboarding agent",
    body: "New members get a structured walkthrough rooted in your SOPs — checklist, citations, and questions answered from real lab documents.",
  },
  {
    icon: <ShieldCheck className="h-5 w-5" />,
    tint: "bg-violet-50 text-violet-600",
    title: "Role-based access",
    body: "Owner, Admin, Member, Viewer — enforced at the API. Cross-lab data leakage is impossible by construction, not by convention.",
  },
  {
    icon: <FileText className="h-5 w-5" />,
    tint: "bg-amber-50 text-amber-700",
    title: "Document intelligence",
    body: "Drop SOPs and policies into a lab. Lexical and embedding retrievers answer questions with citations linked back to the source.",
  },
  {
    icon: <Workflow className="h-5 w-5" />,
    tint: "bg-blue-50 text-blue-600",
    title: "Pluggable providers",
    body: "Swap LLMs, retrievers, and storage backends behind a Protocol. Mock for tests, OpenAI for prod, local for offline. One config flag.",
  },
  {
    icon: <Layers className="h-5 w-5" />,
    tint: "bg-rose-50 text-rose-600",
    title: "Versioned artifacts",
    body: "Every iteration is captured. Diff specs across turns, roll back to any prior version, or fork into a new session entirely.",
  },
];

function Modules() {
  return (
    <section id="platform" className="py-32">
      <div className="mx-auto max-w-[1280px] px-6">
        <div className="mx-auto max-w-2xl text-center fade-in-up">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
            Platform
          </p>
          <h2 className="mt-3 text-4xl font-extrabold tracking-[-0.02em] text-slate-900">
            One system. Every lab workflow.
          </h2>
          <p className="mt-4 text-lg leading-[1.625] text-slate-600">
            LabSmith collapses CAD, onboarding, document search, and access control
            into a single audited surface that your PIs and your IT review board can
            both sign off on.
          </p>
        </div>

        <div className="mt-16 grid gap-5 md:grid-cols-2 lg:grid-cols-3">
          {MODULES.map((m) => (
            <div
              key={m.title}
              className="group relative overflow-hidden rounded-[12px] border border-slate-200 bg-white p-6 transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)] hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-xl hover:shadow-slate-200/50"
            >
              <div className={`grid h-10 w-10 place-items-center rounded-[8px] ${m.tint}`}>
                {m.icon}
              </div>
              <h3 className="mt-5 text-base font-bold text-slate-900">{m.title}</h3>
              <p className="mt-2 text-sm leading-[1.625] text-slate-600">{m.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Stats                                                                      */
/* -------------------------------------------------------------------------- */

function Stats() {
  return (
    <section className="relative overflow-hidden bg-[#020617] py-32">
      {/* Concentric circles */}
      <div className="pointer-events-none absolute inset-0 grid place-items-center">
        {[0, 1, 2, 3, 4].map((i) => (
          <span
            key={i}
            className="absolute aspect-square rounded-full border border-white/10"
            style={{ width: `${(i + 1) * 280}px` }}
          />
        ))}
      </div>

      <div className="relative mx-auto max-w-[1280px] px-6">
        <div className="mx-auto max-w-2xl text-center fade-in-up">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-400">
            Quantifiable impact
          </p>
          <h2 className="mt-3 text-4xl font-extrabold tracking-[-0.02em] text-white">
            Measured against the way labs work today.
          </h2>
        </div>

        <div className="mt-16 grid grid-cols-2 gap-y-12 lg:grid-cols-4">
          <Kpi
            value={94}
            format="percent"
            label="Reduction in CAD time"
            note="Median across 12 pilot labs, vs. SolidWorks workflow"
          />
          <Kpi
            value={3200}
            format="suffix"
            suffix="+"
            label="Parts generated"
            note="Cumulative across active workspaces, M9 release"
          />
          <Kpi
            value={99.97}
            format="percent"
            label="Uptime SLA"
            note="Rolling 90-day, region us-east-1"
          />
          <Kpi
            value={148}
            format="suffix"
            suffix=" labs"
            label="On the platform"
            note="Joined in the last two quarters"
          />
        </div>
      </div>
    </section>
  );
}

function Kpi({
  value,
  format,
  suffix,
  label,
  note,
}: {
  value: number;
  format: "int" | "percent" | "suffix";
  suffix?: string;
  label: string;
  note: string;
}) {
  return (
    <div className="text-center">
      <p className="text-5xl font-extrabold tracking-[-0.02em] text-[#60a5fa] md:text-6xl">
        <KpiCounter value={value} format={format} suffix={suffix} />
      </p>
      <p className="mt-3 text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">
        {label}
      </p>
      <p className="mx-auto mt-2 max-w-[220px] text-xs leading-relaxed text-slate-500">
        {note}
      </p>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Security                                                                   */
/* -------------------------------------------------------------------------- */

const CERTS = [
  { title: "SOC 2 Type II (in audit)", body: "Continuous controls monitoring across infra, change management, and access." },
  { title: "GDPR & CCPA aligned", body: "Data residency, deletion-on-request, and a documented sub-processor list." },
  { title: "Per-lab data isolation", body: "Membership scoping enforced at the API. No shared embedding indices between labs." },
  { title: "Bring your own LLM key", body: "Run on your OpenAI, Azure OpenAI, or self-hosted endpoint. Your prompts, your retention." },
];

function Security() {
  return (
    <section id="security" className="py-32">
      <div className="mx-auto max-w-[1280px] px-6">
        <div className="grid gap-16 lg:grid-cols-2 lg:items-center">
          <div className="fade-in-up">
            <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
              Security & compliance
            </p>
            <h2 className="mt-3 text-4xl font-extrabold tracking-[-0.02em] text-slate-900">
              Designed for institutional review.
            </h2>
            <p className="mt-4 text-lg leading-[1.625] text-slate-600">
              The surface area your security team actually cares about — auditability,
              data isolation, and credential hygiene — is the surface area we built first.
            </p>

            <ul className="mt-8 space-y-4">
              {CERTS.map((c) => (
                <li key={c.title} className="flex items-start gap-3">
                  <CheckCircle2 className="mt-0.5 h-5 w-5 shrink-0 text-[#2563eb]" />
                  <div>
                    <p className="text-sm font-semibold text-slate-900">{c.title}</p>
                    <p className="mt-0.5 text-sm leading-[1.625] text-slate-600">{c.body}</p>
                  </div>
                </li>
              ))}
            </ul>
          </div>

          {/* Right column: policy toggle card with overlapping alert */}
          <div className="relative">
            <div className="rounded-[12px] border border-slate-200 bg-white p-6 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-500">
                    lab/yamamoto · security policies
                  </p>
                  <h3 className="mt-1 text-base font-bold text-slate-900">
                    Active controls
                  </h3>
                </div>
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
                  <span className="status-dot !h-1.5 !w-1.5" />
                  Healthy
                </span>
              </div>

              <div className="mt-2 divide-y divide-slate-100">
                <PolicyToggle
                  defaultOn
                  label="Multi-factor authentication"
                  description="Enforced for owner and admin roles across all labs."
                />
                <PolicyToggle
                  defaultOn
                  label="IP allowlist"
                  description="Limit member sign-ins to your campus or VPN ranges."
                />
                <PolicyToggle
                  label="Quarterly key rotation"
                  description="Auto-rotate API and service-account credentials every 90 days."
                />
                <PolicyToggle
                  defaultOn
                  label="Audit log SIEM export"
                  description="Stream events to Splunk, Datadog, or any S3-compatible sink."
                />
              </div>
            </div>

            {/* Overlapping alert card */}
            <div className="pointer-events-none absolute -bottom-8 -right-6 hidden w-[280px] rounded-[12px] border border-slate-700 bg-slate-800 p-4 text-white shadow-2xl shadow-slate-900/40 sm:block">
              <div className="flex items-center gap-2">
                <span className="grid h-7 w-7 place-items-center rounded-md bg-red-500/15 text-red-400">
                  <KeyRound className="h-3.5 w-3.5" />
                </span>
                <p className="text-xs font-semibold uppercase tracking-[0.06em] text-slate-300">
                  Threat blocked
                </p>
              </div>
              <p className="mt-3 text-sm leading-snug">
                3 sign-in attempts from an unrecognized region were blocked and the
                affected member was notified.
              </p>
              <p className="mt-2 text-[11px] text-slate-400">12 seconds ago · iam/sso-saml</p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* FAQ                                                                        */
/* -------------------------------------------------------------------------- */

function FaqSection() {
  return (
    <section id="faq" className="bg-slate-50 py-32">
      <div className="mx-auto max-w-[960px] px-6">
        <div className="text-center fade-in-up">
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-blue-600">
            Frequently asked
          </p>
          <h2 className="mt-3 text-4xl font-extrabold tracking-[-0.02em] text-slate-900">
            What labs ask before they roll us out.
          </h2>
        </div>
        <div className="mt-12">
          <Faq />
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* CTA                                                                        */
/* -------------------------------------------------------------------------- */

function Cta({ isSignedIn }: { isSignedIn: boolean }) {
  return (
    <section className="py-32">
      <div className="mx-auto max-w-[1280px] px-6">
        <div className="relative overflow-hidden rounded-[12px] border border-slate-200 bg-[#020617] px-10 py-16 text-center md:px-16 md:py-20">
          <div className="grid-bg-dark pointer-events-none absolute inset-0 opacity-50" />
          <div className="pointer-events-none absolute inset-x-0 -bottom-32 mx-auto h-[280px] max-w-[600px] rounded-full bg-blue-600/30 blur-3xl" />
          <div className="relative">
            <h2 className="mx-auto max-w-2xl text-4xl font-extrabold tracking-[-0.02em] text-white md:text-5xl">
              Bring LabSmith to your lab in under a day.
            </h2>
            <p className="mx-auto mt-5 max-w-xl text-base leading-[1.625] text-slate-300">
              Spin up a workspace, invite your PI, and upload your first SOP. We&apos;ll
              walk you through deployment options and answer any compliance questions.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                href={isSignedIn ? "/dashboard/labs" : "/sign-up"}
                className="inline-flex h-11 items-center gap-2 rounded-[8px] bg-[#2563eb] px-6 text-sm font-semibold text-white transition-all duration-200 ease-[cubic-bezier(0.4,0,0.2,1)] hover:bg-[#1d4ed8]"
              >
                {isSignedIn ? "Open your dashboard" : "Get started for free"}
                <ArrowRight className="h-4 w-4" />
              </Link>
              <a
                href="mailto:hello@labsmith.io"
                className="inline-flex h-11 items-center rounded-[8px] border border-white/15 bg-white/5 px-6 text-sm font-semibold text-white backdrop-blur transition-colors hover:bg-white/10"
              >
                Talk to founders
              </a>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/* Footer                                                                     */
/* -------------------------------------------------------------------------- */

function Footer() {
  return (
    <footer className="border-t border-slate-200 bg-white">
      <div className="mx-auto max-w-[1280px] px-6 py-16">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-6">
          <div className="col-span-2">
            <Link href="/" className="flex items-center gap-2.5">
              <span className="grid h-7 w-7 place-items-center rounded-md bg-[#020617] text-white">
                <FlaskConical className="h-3.5 w-3.5" />
              </span>
              <span className="text-[15px] font-bold tracking-tight">LabSmith</span>
            </Link>
            <p className="mt-4 max-w-xs text-sm leading-[1.625] text-slate-500">
              The operating system for modern wet labs. Conversational CAD, onboarding,
              and audited access — in one place.
            </p>
            <p className="mt-6 text-xs text-slate-400">
              San Francisco, CA · Cambridge, MA
            </p>
            <div className="mt-4 flex items-center gap-2">
              <SocialIcon label="GitHub" />
              <SocialIcon label="X" />
              <SocialIcon label="LinkedIn" />
            </div>
          </div>

          <FooterCol
            title="Product"
            links={["Platform overview", "Conversational CAD", "Onboarding agent", "Document search", "Changelog"]}
          />
          <FooterCol
            title="Resources"
            links={["Documentation", "API reference", "Sample SOPs", "Deployment guide", "Status"]}
          />
          <FooterCol
            title="Company"
            links={["About", "Careers", "Press", "Contact", "Brand kit"]}
          />
          <FooterCol
            title="Legal"
            links={["Terms", "Privacy", "Data processing addendum", "Sub-processors", "Responsible disclosure"]}
          />
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-3 border-t border-slate-200 pt-6 text-xs text-slate-500 md:flex-row">
          <p>© {new Date().getFullYear()} LabSmith Labs, Inc. All rights reserved.</p>
          <a
            href="#"
            className="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white px-3 py-1 font-medium text-slate-600 hover:bg-slate-50"
          >
            <span className="status-dot" />
            All systems operational
          </a>
        </div>
      </div>
    </footer>
  );
}

function FooterCol({ title, links }: { title: string; links: string[] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-[0.08em] text-slate-900">
        {title}
      </p>
      <ul className="mt-4 space-y-2.5 text-sm">
        {links.map((l) => (
          <li key={l}>
            <a href="#" className="text-slate-500 transition-colors hover:text-slate-900">
              {l}
            </a>
          </li>
        ))}
      </ul>
    </div>
  );
}

function SocialIcon({ label }: { label: string }) {
  const Icon =
    label === "GitHub" ? Cpu : label === "LinkedIn" ? Beaker : ShieldCheck;
  return (
    <a
      href="#"
      aria-label={label}
      className="grid h-8 w-8 place-items-center rounded-md border border-slate-200 text-slate-500 transition-colors hover:border-slate-300 hover:text-slate-900"
    >
      <Icon className="h-3.5 w-3.5" />
    </a>
  );
}
