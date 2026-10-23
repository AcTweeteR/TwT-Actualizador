# Trakt TMDb directed discovery — 2026-10-23

Status: **PARTIAL; no restore is authorized**.

- Input: verified read-only Trakt snapshot (1,034 unique movie TMDb IDs, 17 unique show TMDb IDs for 796 episodes).
- Catalog: XStream profile 1, read-only.
- TMDb live GET detail queries: 1,051 total.
- Movie candidates with exactly one provider stream ID after exact localized title/year comparison: **889**.
- Movie unmatched: **132**; multiple distinct provider streams: **10**; HTTP errors: **3**.
- Show candidates: **17 of 17**.
- **906 candidate works total. These are NOT verified restoration identities.**
- Candidate evidence uses TMDb titles and year; original-title fallback was added after the full scan started and needs a rerun to quantify impact.
- Episode inventory: only 2 of the 17 matched show IDs have complete inventories locally; the other 15 cannot be mapped safely without further Xtream evidence.
- Tests: 518 passed/ran without failures; 2 skipped (with a prior XStream beta1 candidate ZIP provided for the ZIP-dependent test). A beta2 package still requires its own validation.
- Code: `trakt_tmdb_discovery.py` performs explicit opt-in read-only discovery. The restore importer deliberately does not accept these candidates as verified.
- No watched/resume changes, no Trakt POST, no Kodi installation, no repo publication.

Next required: validate provider-bound identities using XStream detail endpoints/caches, fill episode inventories for all series, integrate only verified identities into `prepare_restore`, then rerun full offline preview and Kodi runtime tests. The previous Xtream connection timeout remains unverified as resolved.
