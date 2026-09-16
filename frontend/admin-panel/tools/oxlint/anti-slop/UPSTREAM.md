# Vendored anti-slop installation

Source: [dmmulroy/anti-slop](https://github.com/dmmulroy/anti-slop), skill `install-anti-slop`.
Installed via the `skills` CLI (`npx skills add dmmulroy/anti-slop --skill install-anti-slop`),
which does not surface the exact source commit — recorded as unknown rather than guessed.
Skill package identity/hash: see `install-anti-slop` entry in the repo root's `skills-lock.json`.

Installed plugin path: `tools/oxlint/anti-slop/` (this directory), registered in
`.oxlintrc.json` as the `anti-slop` jsPlugin. Only the generic ruleset is enabled — the
optional Effect plugin (`anti-slop-effect/*`) was not registered, since this project has no
`effect` dependency.

## Intentional deviations

None yet — fresh install, no local rule edits.

## Known limitation

Oxlint's JS plugin loader needs Node's native TypeScript stripping to import
`tools/oxlint/anti-slop/index.ts` directly, which requires **Node ≥22** — the project's own
Docker images use `node:20-alpine` for the Vite dev server and build (that part is unaffected,
`npm run build` doesn't load this plugin). Run `npm run lint` with a local Node ≥22, or in a
one-off `node:22-alpine` container, not inside the project's existing `node:20-alpine` services.
