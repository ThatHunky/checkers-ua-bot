# Matchmaking Design

## Goals
- Separate rated and casual queues.
- Prevent double-matching and stale tickets.
- Support invite codes for private games.

## Redis Schema
- `mm:queue:{mode}` (ZSET) — members are `user_id`, score is rating.
- `mm:ticket:{user_id}` (HASH) — `mode`, `chat_id`, `created_at`, `rating`, `status`, `opponent`, `match_id`.
- `mm:match:{match_id}` (HASH) — transient record of a pairing; expires after 120s.
- `mm:invite:{code}` (HASH) — invite metadata with status `open|used`; expires after 30m (10m after accept).

## State Machine
1. **enqueue** → ticket stored as `queued`, user added to queue.
2. **matched** → pairing Lua script removes both members, updates tickets to `matched`, and writes `mm:match:*`.
3. **cancel/expire** → queue removal + ticket status `cancelled`.
4. **cleanup** → remove queue entry and ticket after game creation or error.

## Matching Algorithm
1. Read queued members ordered by rating.
2. For each user compute allowed delta = `BASE_DELTA + STEP * floor(wait/STEP_SECONDS)`, capped at `MAX_DELTA`.
3. Choose closest opponent within delta.
4. Finalize via Lua script (verifies both tickets still queued and present in ZSET, then removes them atomically).

Defaults: `BASE_DELTA=50`, `STEP=50`, `STEP_SECONDS=10`, `MAX_DELTA=400`.

## Invite Flow
- Creator calls `mm_create_invite` to store `open` invite with TTL 30m.
- Joiner calls `mm_accept_invite`, which atomically flips status to `used`, records opponent IDs/chats, and sets 10m TTL.
- Handler starts a private game using stored chat IDs; on failure, call `mm_cleanup_user` for both players.

## Failure & Recovery
- Stale tickets expire automatically (15 minutes enqueue, 5 minutes after cancel/finish).
- If bot cannot message a player, game creation aborts, tickets are cleaned, and the available user can be re-queued.
- Background matcher job can periodically call `mm_try_match` to drain queues.

## Manual Test Checklist
- Start two users, open main menu, choose **Quick Match (Rated)** on both; ensure pairing message appears and board sent.
- Repeat for **Quick Match (Casual)**.
- Create invite (rated), share code, join via `/join CODE`; verify game starts for both chats.
- Press **Cancel** while searching; ticket should disappear and play menu returns.
- Attempt to queue while an active game exists; bot should refuse with warning.
- Block bot or close chat for one user before game start; other user should be cleaned from queue and can re-queue.
