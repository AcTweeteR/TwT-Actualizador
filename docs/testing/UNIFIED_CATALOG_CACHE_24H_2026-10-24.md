# Unified Catalog Cache 24H — Testing

Candidate tested on 2026-10-24. Testing-only versions:

- AcTweeteR Service `0.4.70` — SHA-256 `3bfd0d75ef28dfb3825523e6b495427f13f26d74d3f88ddcbd0694bb5ccc39c6`.
- XStream Pro `1.1.2.28~beta10` — SHA-256 `80d0dcda256bcd739d1b753c02f3e70f0d843fdcd6f3348ff3af645d014a4c8c`.
- Skin `1.2.32~beta1` is unchanged from the preceding Testing feed.

Movie and series streams/categories are fetched, validated, staged, and activated as one immutable catalog generation. A failed component leaves the previous generation active. Per-provider/profile OS locks coordinate independent Kodi Python processes; interrupted owners release the lock automatically. Smart Search refresh remains transactional across movie and series rows.

Validation: 601 tests and 52 subtests passed with the exact candidate and pinned upstream ZIP; ZIP CRC, packaged Python syntax, XML, and reproducible XStream hashes passed. The upstream ZIP hash remains `915f45708670d07e789bb73b7390a7b5cf30175f818ef5da8ea18c9f13f537fe`.

Stable was not modified. Kodi Mac Master verification is performed after installation from the official Testing repository.