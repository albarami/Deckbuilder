# DeckForge Frontend

Next.js 14 + React 18 + TypeScript + Tailwind CSS + Zustand + next-intl (EN/AR).

## Setup

```powershell
npm install
```

## Development

```powershell
npm run dev
```

Opens at `http://localhost:3000`. Requires the backend running on port 8000.

## Environment

Create `.env.local` from the example:

```powershell
copy .env.local.example .env.local
```

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |
| `NEXT_PUBLIC_ENABLE_PPT` | (empty = false) | Enable deck/slides UI (PPT feature flag) |

## Tests

```powershell
# TypeScript check
npx tsc --noEmit

# Run all tests
npx vitest run --reporter=verbose

# Watch mode
npx vitest

# E2E (requires running app)
npx playwright test
```

## Stack

- **Next.js 14** -- App router with `[locale]` prefix
- **React 18** -- Components in `src/components/`
- **TypeScript** -- Strict mode
- **Tailwind CSS** -- SG design tokens (`sg-navy`, `sg-teal`, `sg-slate`, etc.)
- **Zustand** -- Pipeline store with SSE event hydration
- **next-intl** -- EN/AR translations in `src/i18n/messages/`
- **Vitest** -- Unit + component tests
- **Playwright** -- E2E tests
