"use client";

import { ChevronDown } from "lucide-react";
import { useState } from "react";

interface FaqItem {
  q: string;
  a: string;
}

const ITEMS: FaqItem[] = [
  {
    q: "How do you handle our SOPs and protected lab documents?",
    a: "Documents are scoped to the lab they belong to and accessible only to members with the right role. Embeddings are computed per request and not shared across labs. We don't train on your data.",
  },
  {
    q: "What's the path from a chat to a fabrication-ready file?",
    a: "Describe a part in plain language. The agent extracts a typed spec, validates it against fabrication rules, and emits an STL/STEP artifact you can download or send to a printer.",
  },
  {
    q: "Can we bring our own LLM provider?",
    a: "Yes. The backend runs on a pluggable provider Protocol — swap in OpenAI, an Azure deployment, a local Ollama instance, or a stub for offline development. Falls back to a deterministic mock if no key is set.",
  },
  {
    q: "How does role-based access work across labs?",
    a: "Owner, Admin, Member, and Viewer roles are enforced at the API layer. Membership scoping is derived from the session's project, so cross-lab data leakage is impossible by construction.",
  },
  {
    q: "What's the deployment story?",
    a: "Containerized backend, Next.js frontend, and Postgres. Deploy to Render, Fly, or your own Kubernetes cluster. Storage is abstracted — switch from local disk to S3 by changing one config.",
  },
];

export function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <div className="divide-y divide-slate-200 rounded-[12px] border border-slate-200 bg-white">
      {ITEMS.map((item, i) => {
        const isOpen = open === i;
        return (
          <div key={i}>
            <button
              type="button"
              onClick={() => setOpen(isOpen ? null : i)}
              className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left transition-colors duration-200 hover:bg-slate-50"
              aria-expanded={isOpen}
            >
              <span className="text-base font-semibold text-slate-900">{item.q}</span>
              <ChevronDown
                className={[
                  "h-4 w-4 shrink-0 text-slate-500 transition-transform duration-200",
                  isOpen ? "rotate-180" : "",
                ].join(" ")}
              />
            </button>
            <div
              className={[
                "grid overflow-hidden px-6 transition-all duration-300 ease-[cubic-bezier(0.4,0,0.2,1)]",
                isOpen ? "grid-rows-[1fr] pb-5 opacity-100" : "grid-rows-[0fr] opacity-0",
              ].join(" ")}
            >
              <div className="min-h-0 overflow-hidden">
                <p className="text-[15px] leading-[1.625] text-slate-600">{item.a}</p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
