"use client";

import { CheckSquare, FileText, Lightbulb } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { buildApiUrl } from "@/lib/api";
import type {
  OnboardingChecklistItem,
  OnboardingCitation,
  OnboardingTopic,
} from "@/lib/use-chat";

interface OnboardingTurnPanelProps {
  topic: OnboardingTopic | null;
  checklist: OnboardingChecklistItem[];
  citations: OnboardingCitation[];
}

/**
 * Renders the per-turn onboarding-agent metadata: topic classification,
 * suggested checklist steps, and any cited lab documents (M9 retrieval).
 *
 * Renders nothing when none of the three are populated, so the chat panel
 * stays clean when the agent hasn't replied yet.
 */
export function OnboardingTurnPanel({
  topic,
  checklist,
  citations,
}: OnboardingTurnPanelProps) {
  if (!topic && checklist.length === 0 && citations.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      {topic && (
        <Card className="border-l-4 border-l-primary">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Lightbulb className="h-4 w-4" />
              Topic: {topic.label}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-muted-foreground">
            <p>{topic.rationale}</p>
            {topic.suggestedQuestions.length > 0 && (
              <div className="space-y-1">
                <p className="text-xs font-medium uppercase tracking-wide">
                  Try asking
                </p>
                <ul className="list-disc space-y-0.5 pl-5">
                  {topic.suggestedQuestions.map((q) => (
                    <li key={q}>{q}</li>
                  ))}
                </ul>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {checklist.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <CheckSquare className="h-4 w-4" />
              Suggested checklist
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {checklist.map((item) => (
                <li key={item.stepId} className="rounded-md border bg-muted/40 p-3">
                  <p className="text-sm font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">{item.detail}</p>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {citations.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <FileText className="h-4 w-4" />
              Cited lab documents
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {citations.map((citation, index) => (
              <CitationRow
                key={`${citation.documentId ?? "none"}-${index}`}
                citation={citation}
              />
            ))}
            <p className="text-xs text-muted-foreground">
              Citations come from documents uploaded to this lab. Click to open
              the source.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

function CitationRow({ citation }: { citation: OnboardingCitation }) {
  const scoreLabel =
    citation.score !== null ? ` · relevance ${citation.score.toFixed(2)}` : "";

  if (citation.url) {
    let href = citation.url;
    try {
      href = buildApiUrl(citation.url);
    } catch {
      // buildApiUrl throws if the API base URL is misconfigured. Fall through
      // to the raw URL — the link still works for same-origin deploys, and
      // the dashboard's broader API client will surface the misconfiguration
      // separately via its own error path.
    }

    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="block rounded-md border bg-muted/40 p-3 text-sm hover:bg-accent"
      >
        <span className="font-medium">{citation.title}</span>
        <span className="text-xs text-muted-foreground"> · {citation.source}{scoreLabel}</span>
      </a>
    );
  }

  return (
    <div className="rounded-md border bg-muted/40 p-3 text-sm">
      <span className="font-medium">{citation.title}</span>
      <span className="text-xs text-muted-foreground"> · {citation.source}{scoreLabel}</span>
    </div>
  );
}
