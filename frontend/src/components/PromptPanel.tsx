import { FlaskConical, Send } from "lucide-react";
import type { FormEvent } from "react";

interface PromptPanelProps {
  prompt: string;
  isLoading: boolean;
  onPromptChange: (prompt: string) => void;
  onSubmit: () => void;
}

const EXAMPLES = [
  "Create a tissue microarray mold with 96 wells, 1 mm diameter, 2 mm spacing",
  "Design a rack for 1.5 mL tubes that fits in a standard ice bucket",
  "Make a gel electrophoresis comb with 10 wells"
];

export function PromptPanel({
  prompt,
  isLoading,
  onPromptChange,
  onSubmit
}: PromptPanelProps) {
  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    onSubmit();
  }

  return (
    <section className="workspace-pane prompt-pane" aria-labelledby="prompt-title">
      <div className="pane-heading">
        <div className="icon-tile" aria-hidden="true">
          <FlaskConical size={22} />
        </div>
        <div>
          <h1 id="prompt-title">LabSmith</h1>
          <p>Turn laboratory hardware requests into fabrication-ready CAD plans.</p>
        </div>
      </div>

      <form className="prompt-form" onSubmit={handleSubmit}>
        <label htmlFor="lab-prompt">Lab hardware request</label>
        <textarea
          id="lab-prompt"
          value={prompt}
          onChange={(event) => onPromptChange(event.target.value)}
          placeholder="Describe the mold, rack, comb, or fixture you need..."
          rows={8}
        />
        <button className="primary-button" type="submit" disabled={isLoading || !prompt.trim()}>
          <Send size={18} />
          <span>{isLoading ? "Generating" : "Generate plan"}</span>
        </button>
      </form>

      <div className="examples" aria-label="Example prompts">
        {EXAMPLES.map((example) => (
          <button
            key={example}
            type="button"
            className="example-button"
            onClick={() => onPromptChange(example)}
          >
            {example}
          </button>
        ))}
      </div>
    </section>
  );
}
