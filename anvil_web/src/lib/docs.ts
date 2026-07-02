// Documentation links. All docs open in a NEW TAB (target="_blank" rel="noopener").
//
// The backend serves the full reference wiki (docs/ANVIL_WIKI.html) at
// /wiki/ANVIL_WIKI.html, so docs links work offline and always match the
// running code version. The GitHub repo stays available as REPO_URL for
// source browsing.

import { API_BASE } from "./api";

export const REPO_URL = "https://github.com/c-rk/the-anvil-framework";

/** Top-level project docs: the locally served reference wiki. */
export const DOCS_URL = `${API_BASE}/wiki/ANVIL_WIKI.html`;

/**
 * Docs link for a single RSQ.
 *
 * The reference wiki assigns each built-in RSQ an element id equal to its
 * snake_case identifier (e.g. id="isentropic_ratios"), so a plain fragment
 * lands directly on its section. Unknown names still open the wiki itself —
 * graceful degradation rather than a dead link.
 */
export function rsqDocsUrl(name: string): string {
  const anchor = name.trim();
  return anchor ? `${DOCS_URL}#${encodeURIComponent(anchor)}` : DOCS_URL;
}

/** Standard attributes for an external link that opens safely in a new tab. */
export const NEW_TAB = {
  target: "_blank" as const,
  rel: "noopener noreferrer" as const,
};
