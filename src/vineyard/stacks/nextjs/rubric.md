# Next.js Build Rubric

## Project Setup
- `package.json` declares `next`, `react`, `react-dom`, `typescript`, `tailwindcss`, `drizzle-orm` as dependencies
- `tsconfig.json` has `strict: true` and the `@/*` path alias configured
- `next.config.ts` exists and is valid
- `.env.example` lists every env var referenced in the code

## Code Quality
- App Router used throughout; no `pages/` directory
- Client components are explicitly marked with `"use client"`; server components are the default
- Forms use Server Actions, not API routes, for mutations
- Database access goes through `db/index.ts`; no inline connection strings
- Zod schemas validate all external input (form data, route params, env vars)

## Database
- `db/schema.ts` defines all tables with proper relations
- `drizzle.config.ts` is configured for the chosen database
- Migration files are present in `db/migrations/`

## Tests
- At least one Vitest unit test exists under `tests/` or co-located `*.test.ts(x)`
- Test scripts are wired in `package.json` (`test`, `test:watch`)

## Deliverables
- All output files live under `/mnt/session/outputs/`
- A `README.md` explains setup: install, env config, dev server, deploy
- Running `pnpm install && pnpm build` would succeed (no missing imports, no TS errors that would block build)
