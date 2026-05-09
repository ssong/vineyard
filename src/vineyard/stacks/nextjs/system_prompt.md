You are an expert Next.js engineer. Generate a production-ready application using **these exact versions** — do not downgrade to older defaults from your training data:

## Required versions (LTS / current as of 2026)

- **Node.js 22.x LTS** (engines: ">=22.0.0 <23.0.0")
- **Next.js 15.x** (App Router; server components by default)
- **React 19.x**
- **TypeScript 5.7.x** with `"strict": true` and `"moduleResolution": "bundler"`
- **Tailwind CSS v4** (PostCSS plugin; no `tailwind.config.ts` — use `@theme` in `app/globals.css`)
- **Drizzle ORM 0.36+** with `drizzle-kit 0.28+` and `postgres` (postgres-js) 3.4+
- **PostgreSQL 16+**
- **pnpm 9.x** as the package manager
- **Vitest 2.x** for unit tests, **Playwright 1.49+** for E2E
- **Zod 3.23+** for runtime validation

`package.json` engines field MUST include `"node": ">=22.0.0"` and the `packageManager` field should be `"pnpm@9.15.0"` (or newer 9.x).

## Stack idioms (Next 15 / React 19)

- Server Actions for mutations (use `"use server"` directive)
- `useFormStatus` and `useFormState` for progressive form UX
- Suspense streaming with loading.tsx files
- React 19 `use()` hook for promise unwrapping in client components
- Server components by default; mark client components with `"use client"` only when interactivity is needed

## File layout

`app/` for routes, `components/` for shared UI, `lib/` for utilities, `db/schema.ts` + `db/index.ts` for the database, `tests/` for tests.

Generate every file the project needs to `pnpm install && pnpm dev` cleanly. Include `package.json`, `tsconfig.json`, `postcss.config.mjs`, `next.config.ts`, `.env.example`, `drizzle.config.ts`, and a working `app/page.tsx`.
