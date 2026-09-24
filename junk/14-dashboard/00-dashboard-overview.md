# 14 — Dashboard Overview

> Next.js 14 (App Router) + TypeScript + Tailwind CSS + shadcn/ui. Real-time via WebSocket. Auth via JWT.

## Pages

| Page             | Route                   | Purpose                                            |
|------------------|-------------------------|----------------------------------------------------|
| Login            | `/login`                | Email + password                                   |
| Overview         | `/`                     | Portfolio snapshot, today's decisions, key metrics |
| Portfolio        | `/portfolio`            | Holdings, target weights, drift                    |
| Alerts           | `/alerts`               | Inbox of all alerts; mark-as-read                  |
| Decisions        | `/decisions`            | List + detail view with full evidence trace        |
| Decision Detail  | `/decisions/[id]`       | Full trace: evidence, prompts used, compliance     |
| Agents           | `/agents`               | Activity log per agent (last 24h, 7d)              |
| Backtest         | `/backtest`             | Run new backtest, view historical reports          |
| Settings         | `/settings`             | Notification prefs, source toggles, API keys       |
| System Health    | `/health`               | CPU, memory, queue depth, LLM cost                 |

## Tech Stack

- **Framework:** Next.js 14 (App Router, RSC where possible)
- **Language:** TypeScript 5.3+
- **Styling:** Tailwind CSS 4, shadcn/ui components
- **State:** TanStack Query (server state), Zustand (UI state)
- **Realtime:** Native WebSocket (reconnect logic)
- **Auth:** NextAuth.js (JWT, 24h refresh)
- **Charts:** Recharts (composeable, React-friendly)
- **Tables:** TanStack Table (sorting, filtering, virtualization)
- **Forms:** React Hook Form + Zod
