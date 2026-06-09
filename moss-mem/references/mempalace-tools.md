# MemPalace Tool Reference

> ⚠️ **Status for moss-mem users**: This file lists the **MCP tool names** that
> `mempalace-mcp` exposes. moss-mem's primary read/write path is the **CLI**
> (`mempalace <subcmd>`). MCP is optional wiring, not a requirement. If your
> runtime has not registered `mempalace-mcp`, ignore this file and use
> `mempalace --help` / `mempalace instructions <topic>` directly. Several MCP
> tools below (e.g. `mempalace_diary_write`, `mempalace_kg_add`,
> `mempalace_create_tunnel`) have **no CLI equivalent** — they are only
> reachable through the MCP server.

> External reference — moved from SKILL.md (was 80+ lines) to keep the main skill
> focused on workflow, not MemPalace API surface. **Authoritative live source**:
> `mempalace instructions help` and `mempalace --help`. This file is a snapshot
> for offline reading; prefer the live CLI for the latest.

## Read (19 tools)

| Tool | Key Parameters | Purpose |
|------|---------------|---------|
| `mempalace_status` | — | Palace overview, drawer/wing/room counts |
| `mempalace_get_taxonomy` | — | Full wing→room→drawer tree |
| `mempalace_list_wings` | — | All wings with drawer counts |
| `mempalace_list_rooms` | `wing` (opt) | Rooms within a wing |
| `mempalace_list_drawers` | `wing`, `room`, `limit`, `offset` | Paginated drawer list |
| `mempalace_get_drawer` | `drawer_id` | Full drawer content + metadata |
| `mempalace_search` | `query`, `limit`, `wing`, `room`, `max_distance` | Semantic search (ChromaDB) |
| `mempalace_check_duplicate` | `content`, `threshold` | Dedup check before write |
| `mempalace_get_aaak_spec` | — | AAAK dialect specification |
| `mempalace_traverse` | `start_room`, `max_hops` | Walk palace graph |
| `mempalace_find_tunnels` | `wing_a`, `wing_b` (both opt) | Cross-wing connections |
| `mempalace_follow_tunnels` | `wing`, `room` | Room's tunnel connections |
| `mempalace_list_tunnels` | `wing` (opt) | All explicit tunnels |
| `mempalace_graph_stats` | — | Palace graph overview |
| `mempalace_kg_query` | `entity`, `as_of`, `direction` | Temporal KG query |
| `mempalace_kg_timeline` | `entity` (opt) | Chronological fact timeline |
| `mempalace_kg_stats` | — | KG overview: entities, triples |
| `mempalace_diary_read` | `agent_name`, `last_n`, `wing` | Agent diary entries |
| `mempalace_memories_filed_away` | — | Recent palace checkpoint |

## Write (11 tools)

| Tool | Key Parameters | Purpose |
|------|---------------|---------|
| `mempalace_add_drawer` | `wing`, `room`, `content`, `source_file`, `added_by` | Store content (idempotent) |
| `mempalace_update_drawer` | `drawer_id`, `content`, `wing`, `room` | Update drawer |
| `mempalace_delete_drawer` | `drawer_id` | Delete drawer (irreversible) |
| `mempalace_kg_add` | `subject`, `predicate`, `object`, `valid_from`, `valid_to` | Add temporal KG fact |
| `mempalace_kg_invalidate` | `subject`, `predicate`, `object`, `ended` | Mark fact no longer true |
| `mempalace_create_tunnel` | `source_wing`, `source_room`, `target_wing`, `target_room`, `label` | Cross-wing link |
| `mempalace_delete_tunnel` | `tunnel_id` | Remove tunnel |
| `mempalace_diary_write` | `agent_name`, `entry` (AAAK), `topic`, `wing` | Write diary entry |
| `mempalace_sync` | `project_dir`, `wing`, `apply` | Prune stale drawers |
| `mempalace_reconnect` | — | Force reconnect palace DB |
| `mempalace_hook_settings` | `silent_save`, `desktop_toast` | Hook behavior |

## Live verification

When in doubt, prefer the live CLI over this snapshot:

```
mempalace --help                  # top-level subcommand list
mempalace instructions <topic>    # canonical per-subcommand guidance
mempalace_get_aaak_spec (MCP)     # authoritative AAAK format spec
```

Tool names, parameters, and counts may shift across `mempalace` versions — this
file is informational, not a contract.
