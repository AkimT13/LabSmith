# Sample Lab Documents

Six markdown files modeled on the kind of documentation a real wet lab actually
keeps — SOPs, safety policies, naming conventions, roster, access checklists.
Use these to exercise the M9 onboarding agent's retrieval path against
realistic content.

The agent does best-effort UTF-8 decode of stored bytes, so markdown loads
cleanly without any conversion. Each doc is short enough (~300–600 words) that
the lexical retriever produces clear top-1 winners for natural questions.

## Files

| File | Topic |
|------|-------|
| `microscope-sop.md` | `equipment` / `protocols` |
| `waste-handling-policy.md` | `safety` |
| `data-storage-conventions.md` | `data` |
| `lab-roster-and-ownership.md` | `people` |
| `access-and-accounts-checklist.md` | `access` |
| `getting-started-week-one.md` | `getting_started` |

## Test queries — lexical-friendly

The default retriever is **lexical** (TF-IDF over chunked text). It hits the
right document when the query uses vocabulary that's distinctive to the
target doc. These six queries each hit the correct doc as the top result:

| Query | Hits |
|-------|------|
| "How do I reserve the Leica DMi8?" | `microscope-sop.md` |
| "Where do I put biohazard bags?" | `waste-handling-policy.md` |
| "Where should I store raw imaging files?" | `data-storage-conventions.md` |
| "Who is the lab safety officer?" | `lab-roster-and-ownership.md` |
| "How do I get tissue culture access?" | `getting-started-week-one.md` |
| "Walk me through orientation week one" | `getting-started-week-one.md` |

## Test queries — where lexical struggles, semantic helps

These same questions, phrased generically, are exactly the cases where
lexical retrieval picks the wrong doc and the OpenAI embedding path
shines. Try one with `LABSMITH_ONBOARDING_RETRIEVER=lexical` and again
with `LABSMITH_ONBOARDING_RETRIEVER=openai` to feel the difference:

- "How do I book the microscope?" — lexical drifts because "book" and
  "microscope" appear across multiple docs.
- "Who owns the centrifuge?" — Lab Roster has "Beckman J6 centrifuge,
  Yuki Tanaka" but lexical sometimes ranks Microscope SOP higher because
  it has more text overall.
- "What should I do on my first day?" — both Access checklist and
  Getting Started use "first day" / "first week"; embeddings do better
  at the semantic distinction.

## How to upload

The current `LabDocumentCreate` endpoint takes JSON with the file content
in a `content: str` field — no multipart upload yet (M9 follow-up). Easiest
way is via `curl` once you have:

- A running backend (`npm run backend:dev`)
- A lab you're a member of (`<lab_id>`)
- Your Clerk session JWT (`<jwt>`)

```bash
LAB_ID="<your-lab-uuid>"
JWT="<paste-clerk-jwt>"
BASE="http://localhost:8000"

# NOTE: this README itself is a meta-doc and should NOT be uploaded — it
# contains all the example queries verbatim and would pollute retrieval.
# The find command below excludes it.
find docs/sample_lab_documents -maxdepth 1 -name '*.md' -not -name 'README.md' \
  | while read -r f; do
  title="$(head -n1 "$f" | sed 's/^# *//')"
  filename="$(basename "$f")"
  content="$(cat "$f")"

  curl -sS -X POST \
    -H "Authorization: Bearer $JWT" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg title "$title" \
      --arg fname "$filename" \
      --arg content "$content" \
      '{title:$title, source_filename:$fname, content_type:"text/markdown", content:$content}')" \
    "$BASE/api/v1/labs/$LAB_ID/documents"
  echo
done
```

(Requires `jq`. On macOS: `brew install jq`.)

## How to verify retrieval is working

1. Upload at least one of these docs to a lab.
2. Create an **onboarding** session in the same lab (use the session-type
   picker — not "part design").
3. Ask one of the example queries above in the chat.

You should see in the chat:
- A `topic_suggested` event matching the query's topic.
- 3 × `checklist_step` events.
- One or more `doc_referenced` events with the matching document's title
  and a download URL — this is the new M9 retrieval signal.
- The streamed assistant reply now contains a "Based on your lab documents"
  section with snippets and a "Sources cited above" footer.

If you don't see `doc_referenced` events, retrieval scored every chunk at
zero — try a query whose vocabulary overlaps with the doc's content. The
default retriever is **lexical** (TF-IDF style); switch to OpenAI
embeddings if you want semantic match for paraphrases:

```
LABSMITH_OPENAI_API_KEY=sk-proj-...
LABSMITH_ONBOARDING_RETRIEVER=openai
```

Then restart the backend.

## Cross-lab isolation check

Upload `microscope-sop.md` to **Lab A** and create an onboarding session in
**Lab B**. Asking "How do I book the microscope?" in Lab B's session must
NOT cite Lab A's document. (This is enforced by the
`test_onboarding_does_not_retrieve_other_lab_documents` regression test.)
