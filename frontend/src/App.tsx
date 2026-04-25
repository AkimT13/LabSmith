import { useEffect, useState } from "react";

import { createDesign, fetchTemplates } from "./api/client";
import type { DesignResponse, TemplateSpec } from "./api/types";
import { PromptPanel } from "./components/PromptPanel";
import { ResultPanel } from "./components/ResultPanel";

const INITIAL_PROMPT =
  "Create a tissue microarray mold with 96 wells, 1 mm diameter, 2 mm spacing";

export default function App() {
  const [prompt, setPrompt] = useState(INITIAL_PROMPT);
  const [result, setResult] = useState<DesignResponse | null>(null);
  const [templates, setTemplates] = useState<TemplateSpec[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  useEffect(() => {
    fetchTemplates()
      .then(setTemplates)
      .catch(() => {
        setTemplates([]);
      });
  }, []);

  async function handleSubmit() {
    if (!prompt.trim()) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      setResult(await createDesign(prompt.trim()));
    } catch (caughtError) {
      setResult(null);
      setError(caughtError instanceof Error ? caughtError.message : "Unable to generate plan.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <main className="app-shell">
      <div className="top-bar">
        <span>LabSmith</span>
        <span>{templates.length ? `${templates.length} templates ready` : "Backend disconnected"}</span>
      </div>
      <div className="workspace">
        <PromptPanel
          prompt={prompt}
          isLoading={isLoading}
          onPromptChange={setPrompt}
          onSubmit={handleSubmit}
        />
        <ResultPanel result={result} error={error} />
      </div>
    </main>
  );
}
