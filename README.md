# withings-mcp

MCP server for Withings. Gives Claude access to your body composition, activity, workouts, and sleep data so you can track trends, spot patterns, and ask questions directly in conversation.

**Runs locally. Your data never leaves your machine.**

---

## Setup

### 1. Create a Withings API application

Go to [https://developer.withings.com/](https://developer.withings.com/) and sign in, then create a new application:

| Field | What to enter |
|---|---|
| **Application name** | Anything, e.g. `local_mcp` |
| **Description** | Anything, e.g. `Local MCP server for Claude` |
| **Callback URI** | `http://localhost:8766` — **this one matters** |
| **Scopes** | `user.info`, `user.metrics`, `user.activity` |

Copy the **Client ID** and **Client Secret** from the app details page.

### 2. Install

```bash
pip install withings-mcp
```

> Requires Python 3.11+

Or from source:

```bash
git clone https://github.com/IcaroBichir/mcp_withings
cd mcp_withings
pip install -e .
```

### 3. Authenticate

Make your credentials available — either as environment variables:

```bash
export WITHINGS_CLIENT_ID=your_client_id
export WITHINGS_CLIENT_SECRET=your_client_secret
```

Or in a `.env` file in your **current working directory**:

```
WITHINGS_CLIENT_ID=your_client_id
WITHINGS_CLIENT_SECRET=your_client_secret
```

Then run:

```bash
withings-mcp auth
```

This opens your browser, completes the Withings OAuth flow, and stores tokens at `~/.config/withings-mcp/tokens.json`. Tokens refresh automatically — you only need to run this once.

### 4. Add to Claude

**Claude Desktop** — edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "withings": {
      "command": "withings-mcp",
      "args": ["serve"]
    }
  }
}
```

**Claude Code** — edit `.claude/settings.json` in your project (or global `~/.claude/settings.json`):

```json
{
  "mcpServers": {
    "withings": {
      "command": "withings-mcp",
      "args": ["serve"]
    }
  }
}
```

Restart Claude after editing the config.

---

## Available tools

| Tool | Default range | Description |
|---|---|---|
| `get_measurements` | Last 30 days | Body composition from the scale: weight, fat ratio, fat mass, fat-free mass, muscle mass, bone mass, hydration |
| `get_activity_summary` | Last 7 days | Daily totals from activity trackers: steps, distance, calories, active time by intensity, HR stats |
| `get_workouts` | Last 30 days | Recorded workout sessions: sport type, duration, distance, calories, HR |
| `get_sleep_summary` | Last 7 days | Nightly sleep data: score, total time, deep/light/REM durations, wake count, HR, respiratory rate |

> **Device note:** `get_activity_summary` and `get_workouts` require a Withings activity tracker (ScanWatch, Steel HR, etc.). They return empty results on scale-only setups (Body Smart, Body Comp).

All tools accept optional `start` and `end` parameters in ISO 8601 format (`YYYY-MM-DD`). Results are always returned newest first.

---

## Local cache

All API responses are cached locally in `~/.config/withings-mcp/cache.db` (SQLite).

| Data type | TTL |
|---|---|
| Body measurements | 24 hours |
| Activity summaries (past days) | 24 hours |
| Activity summaries (today) | 15 minutes |
| Workouts (past days) | 24 hours |
| Workouts (today) | 15 minutes |
| Sleep summaries (past days) | 24 hours |
| Sleep summaries (today) | 15 minutes |

**Cache commands:**

```bash
withings-mcp cache stats   # show entry count and file size
withings-mcp cache clear   # wipe all cached responses
```

---

## Example prompts

Once connected, try asking Claude:

- *"Show me my weight and body fat trend over the last 3 months"*
- *"How has my muscle mass changed since January?"*
- *"What's my average sleep score this week vs last week?"*
- *"How many hours of deep sleep am I averaging?"*
- *"Show me my step count and active calories for the past 7 days"*
- *"Compare my body composition today vs 30 days ago"*

---

## Tests

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/pytest tests/ -v
```

17 tests covering all 4 tool functions and the shared date-range helper. No network calls — `WithingsClient` is mocked.

---

## License

MIT
