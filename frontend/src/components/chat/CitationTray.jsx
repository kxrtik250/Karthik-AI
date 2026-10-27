export default function CitationTray({ citations, onSelectCitation }) {
  if (!citations || citations.length === 0) return null;

  // Deduplicate citations by filename and valid page_number, keeping highest similarity score
  const dedupedCitations = [];
  const seenMap = new Map();

  for (const cite of citations) {
    if (!cite || !cite.filename) continue;

    // Validate page number: only display if positive integer
    const rawPage = cite.page_number;
    const hasValidPage =
      rawPage !== null &&
      rawPage !== undefined &&
      typeof rawPage === "number" &&
      Number.isInteger(rawPage) &&
      rawPage > 0;
    const validPage = hasValidPage ? rawPage : null;

    const key = `${cite.filename.toLowerCase()}::${validPage ?? "none"}`;
    const existing = seenMap.get(key);

    if (!existing) {
      const item = { ...cite, page_number: validPage };
      seenMap.set(key, item);
      dedupedCitations.push(item);
    } else {
      const existingScore = typeof existing.similarity_score === "number" ? existing.similarity_score : -1;
      const newScore = typeof cite.similarity_score === "number" ? cite.similarity_score : -1;
      if (newScore > existingScore) {
        existing.similarity_score = cite.similarity_score;
        existing.snippet = cite.snippet || existing.snippet;
        existing.chunk_index = cite.chunk_index;
      }
    }
  }

  if (dedupedCitations.length === 0) return null;

  return (
    <div className="citation-tray">
      <span className="citation-tray-label">Referenced Sources:</span>
      <div className="citation-chips">
        {dedupedCitations.map((cite, idx) => {
          const hasPage =
            cite.page_number !== null &&
            cite.page_number !== undefined &&
            typeof cite.page_number === "number" &&
            Number.isInteger(cite.page_number) &&
            cite.page_number > 0;

          return (
            <button
              key={`${cite.document_id || cite.filename}-${cite.page_number ?? idx}`}
              type="button"
              className="citation-chip"
              onClick={() => onSelectCitation(cite)}
              title={hasPage ? `Click to view details from ${cite.filename} (page ${cite.page_number})` : `Click to view details from ${cite.filename}`}
            >
              <span className="chip-icon" aria-hidden="true">📄</span>
              <span className="chip-name">{cite.filename}</span>
              {hasPage && (
                <>
                  <span className="chip-sep" aria-hidden="true">•</span>
                  <span className="chip-page">p. {cite.page_number}</span>
                </>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}
