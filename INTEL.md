# Intelligence Workspace (offline multi-mode chatbot)

Open WebUI ships with a built-in **Intelligence** workspace (`/intel`) that gives you a
professional, fully offline chatbot with three modes:

| Mode                    | What it is                                                                                                                                                                            | Data source               |
| ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| **Topic Expert**        | A dedicated expert chat about _topic X_ (economics, politics, culture, aviation strategy, …). The subject, persona and suggested questions live in **one editable file**.             | Your local LLM only       |
| **Flight Intelligence** | A table of the **latest state per aircraft** from Elasticsearch with a time-range filter, search, an **offline map with trajectories**, and a chat grounded in the selected aircraft. | Elasticsearch (read-only) |
| **File Analyst**        | Upload PDF/DOCX/CSV/JSON/Markdown/text files and ask questions about them. Passages are retrieved locally and cited in the answer.                                                    | Open WebUI file storage   |

Nothing calls a cloud service. The browser talks only to your Open WebUI backend, the
backend talks only to your Elasticsearch and your local model (Ollama or any
OpenAI-compatible server).

<table>
<tr><td><b>English</b></td><td>The Intelligence workspace is available from the sidebar after updating. Open <code>/intel</code>, pick a workspace once, and switch tabs at any time.</td></tr>
<tr><td><b>فارسی</b></td><td>فضای «اطلاعات و تحلیل» پس از به‌روزرسانی در نوار کنار سایت ظاهر می‌شود. آدرس <code>/intel</code> را باز کن، یک‌بار حالت دلخواه را انتخاب کن و هر زمان بین سه تب جابه‌جا شو. رابط کاربری با زبان Open WebUI (فارسی/انگلیسی) هماهنگ است.</td></tr>
</table>

---

## 1. Quick start (offline)

```bash
# 1) a local model
ollama serve
ollama pull llama3.1:8b        # or any model you prefer

# 2) Open WebUI
git checkout <this-branch>
pip install -e .               # or use the Docker image built from this tree
open-webui serve

# 3) point the workspace at Elasticsearch (optional, see §3)
export INTEL_ELASTICSEARCH_URL=http://localhost:9200
export INTEL_ELASTICSEARCH_INDEX=flights
export ELASTICSEARCH_USERNAME=elastic
export ELASTICSEARCH_PASSWORD=changeme

open http://localhost:8080/intel
```

If no Elasticsearch URL is configured, the Flight Intelligence tab starts in **demo
mode** with a synthetic dataset (clearly labelled in the UI) so you can explore the map,
table and chat before wiring your real index. Disable it with `INTEL_DEMO_MODE=off`.

---

## 2. The three modes

### 2.1 Topic Expert — change “topic X”

Everything about the expert tab is defined in:

```
src/lib/intel/topic.ts
```

- `ACTIVE_TOPIC_ID` selects which topic is active.
- Four ready-made topics are included: `strategic` (aviation & geopolitics),
  `economics`, `politics`, `culture`. Each has a badge, a bilingual name/description,
  a **system prompt** and suggested questions.

To create your own subject, add an entry to `TOPICS`:

```ts
{
  id: 'energy',
  badge: 'EN',
  name: { en: 'Energy Markets', fa: 'بازار انرژی' },
  tagline: { en: '…', fa: '…' },
  description: { en: '…', fa: '…' },
  systemPrompt: { en: `You are …`, fa: `تو … هستی` },
  suggestions: { en: ['…'], fa: ['…'] }
}
```

…then set `export const ACTIVE_TOPIC_ID = 'energy';`. Rebuild/refresh the browser.

**No rebuild?** Override the prompt at runtime with environment variables:

```bash
INTEL_TOPIC_NAME="Energy Markets"
INTEL_TOPIC_PROMPT="You are a senior energy analyst …"
INTEL_TOPIC_SUGGESTIONS="How do LNG spreads work?,What is a marginal barrel?"
```

The environment override wins over the file, which is handy for per-deployment prompts.

### 2.2 Flight Intelligence — table, time filter, map, chat

- **Default view is the last 24 hours** (configurable with
  `INTEL_DEFAULT_LOOKBACK_HOURS`). Presets: 1 h, 6 h, 24 h, 7 days, plus a custom
  `from`/`to` range with a datetime picker.
- The table shows **one row per aircraft** (the most recent document per id), with
  callsign, route, status, altitude, speed and last-seen time. Full-text search filters
  callsign / route / status / any configured query field.
- Selecting aircraft (checkbox, row click, or “Select all”) draws:
  - the aircraft’s **current position** as a heading-rotated marker with a callsign tooltip;
  - its **`trajectory`** as a coloured polyline with a start marker;
  - every other aircraft in the window as a muted dot for spatial context.
- The map uses a **bundled vector basemap** (Natural Earth 110m via `world-atlas`), so it
  works with no internet and no tile server. If you prefer your own map server, set
  `INTEL_MAP_TILE_URL` (e.g. an internal OSM/MapTiler tile endpoint).
- The chat panel is grounded in the current table + selected trajectories. Every answer
  lists the aircraft/sources it used. There is an “Analyse selection” shortcut that asks
  for a comparison of the selected aircraft.

How the data is read (read-only):

| Parameter                                                       | Default                                                                    | Meaning                                     |
| --------------------------------------------------------------- | -------------------------------------------------------------------------- | ------------------------------------------- |
| `INTEL_TIME_FIELD`                                              | auto (`@timestamp`, `timestamp`, `time`, any date field)                   | Time filter/sort field                      |
| `INTEL_ID_FIELD`                                                | auto (`flight_id`, `icao24`, `id`, `callsign`, …)                          | Aircraft identity used to de-duplicate rows |
| `INTEL_CALLSIGN_FIELD`                                          | auto (`callsign`, `flight`, `name`, …)                                     | Display name of an aircraft                 |
| `INTEL_STATUS_FIELD`                                            | auto (`status`, `state`, `phase`, …)                                       | Status column and filter values             |
| `INTEL_TRAJECTORY_FIELD`                                        | auto (`trajectory`, `track`, `path`, …)                                    | Array/LineString of positions               |
| `INTEL_LAT_FIELD` / `INTEL_LON_FIELD`                           | auto (`lat`/`latitude`, `lon`/`lng`/`longitude`, nested `position.lat`, …) | Current position                            |
| `INTEL_ALT_FIELD` / `INTEL_SPEED_FIELD` / `INTEL_HEADING_FIELD` | auto                                                                       | Extra columns                               |
| `INTEL_QUERY_FIELDS`                                            | auto (all text/keyword fields)                                             | Fields used for search/RAG                  |

Schema detection reads `GET /<index>/_mapping`; the detected mapping is shown in the
**Data source** popover in the UI (top-right chip), which makes mis-detection easy to spot
and override with env vars.

Supported trajectory encodings:

```jsonc
"trajectory": [{"lat": 35.1, "lon": 51.2, "alt": 31000, "timestamp": "2026-10-31T10:00:00Z"}, …]
"trajectory": [[35.1, 51.2], [35.2, 51.3]]            // [lat, lon] (GeoJSON [lon, lat] auto-detected)
"trajectory": {"type": "LineString", "coordinates": [[51.2, 35.1], …]}
"trajectory": {"points": [{"position": {"lat": …}, "time": …}, …]}
"trajectory": "[[35.1, 51.2], …]"                      // JSON encoded string
```

If your index stores one document **per position** instead of a trajectory array, it still
works: the table uses the latest document per aircraft and the trajectory endpoint stitches
all documents of the selected aircraft within the time window into a path.

### 2.3 File Analyst

- Upload one or more files with the existing Open WebUI upload pipeline
  (`/api/v1/files`), so all configured text extractors (PDF, DOCX, XLSX, CSV, …) apply.
- Extracted text is chunked and ranked in the browser with a BM25-style scorer; the most
  relevant passages (≈9k characters) are attached to the question together with a
  `file / chunk` label. The answer cites those labels.
- Files are deleted from storage when you remove them from the panel or clear the tab
  (only files uploaded in this session).
- No embedding model is required, which keeps the mode usable on a machine that only runs
  a chat model. Open WebUI stores the extracted text before it embeds anything, so even if
  the embedding step of the background pipeline fails, the tab still reads the text and
  answers from it.

---

## 3. Configuration reference

All variables are optional except the Elasticsearch connection.

| Variable                                                              | Default                            | Description                                            |
| --------------------------------------------------------------------- | ---------------------------------- | ------------------------------------------------------ |
| `INTEL_ENABLE`                                                        | `true`                             | Master switch. `false` hides the API (404)             |
| `INTEL_ELASTICSEARCH_URL`                                             | `ELASTICSEARCH_URL`                | Elasticsearch base URL                                 |
| `INTEL_ELASTICSEARCH_INDEX`                                           | `ELASTICSEARCH_INDEX` or `flights` | Index / alias to read                                  |
| `INTEL_ELASTICSEARCH_API_KEY`                                         | `ELASTICSEARCH_API_KEY`            | API key auth (takes precedence)                        |
| `INTEL_ELASTICSEARCH_USERNAME` / `_PASSWORD`                          | `ELASTICSEARCH_*`                  | Basic auth                                             |
| `INTEL_ELASTICSEARCH_VERIFY_CERTS`                                    | `true`                             | TLS verification                                       |
| `INTEL_ELASTICSEARCH_CA_CERTS`                                        | `ELASTICSEARCH_CA_CERTS`           | Custom CA bundle                                       |
| `INTEL_ELASTICSEARCH_TIMEOUT`                                         | `20`                               | Request timeout (seconds)                              |
| `INTEL_DEMO_MODE`                                                     | `auto`                             | `auto` = demo only when no URL is set, `on`, `off`     |
| `INTEL_DEFAULT_LOOKBACK_HOURS`                                        | `24`                               | Initial table window                                   |
| `INTEL_MAX_ROWS`                                                      | `500`                              | Max aircraft rows returned                             |
| `INTEL_MAX_TRAJECTORY_DOCS`                                           | `2000`                             | Max documents stitched into one path                   |
| `INTEL_MAX_TRAJECTORY_POINTS`                                         | `1200`                             | Points returned per path (down-sampled)                |
| `INTEL_RAG_TOP_K`                                                     | `8`                                | Documents retrieved per `/search` call                 |
| `INTEL_RAG_MAX_SNIPPET`                                               | `4000`                             | Max characters of a document snippet in search results |
| `INTEL_MAP_TILE_URL`                                                  | –                                  | Use online tiles instead of the bundled vector basemap |
| `INTEL_TOPIC_NAME` / `INTEL_TOPIC_PROMPT` / `INTEL_TOPIC_SUGGESTIONS` | –                                  | Runtime override of the topic tab                      |

The flight and search endpoints also accept per-request limits (`start`, `end`, `hours`,
`size`, `top_k`), which is what the UI uses when you change the time window.

---

## 4. API

All endpoints require a verified Open WebUI session (`Bearer` token or cookie):

```
GET  /api/v1/intel/meta                        feature flags, detected schema, connectivity
GET  /api/v1/intel/flights?hours=24&q=IRB      latest state per aircraft
GET  /api/v1/intel/flights/{id}/trajectory      stitched path for one aircraft
POST /api/v1/intel/search                       document retrieval for RAG
GET  /api/v1/intel/health                       connectivity probe
```

`/search` body:

```json
{ "query": "runway closure impacts", "top_k": 8, "hours": 24, "filters": { "status": "landed" } }
```

The browser composes prompts and calls the normal `/api/chat/completions` endpoint, so
model selection, streaming, and access control are exactly the same as in a normal chat.

---

## 5. Architecture notes

- **One workspace, three modes.** `/intel` opens a chooser the first time (the choice is
  remembered), then a tab bar lets you switch without losing state. Deep links work:
  `/intel?mode=flights`, `?mode=files`, `?mode=topic`.
- **No new services.** The backend addition is a thin Elasticsearch REST client
  (`backend/open_webui/utils/intel.py`) plus a router
  (`backend/open_webui/routers/intel.py`). There is no dependency on the vector DB or the
  embedding pipeline, and no `elasticsearch` Python package is required.
- **Read-only by design.** Only `_search`, `_mapping` and `_count` are used; the
  workspace never writes to Elasticsearch.
- **Why lexical retrieval?** It works with zero extra models, zero GPU and no internet —
  the definition of portable offline. If you later want semantic retrieval, the natural
  upgrade is to add a kNN query inside `IntelService.search()` using your existing
  embedding function. Nothing else has to change.
- **Security.** All routes use `get_verified_user`; index names are URL-quoted and
  validated by the client, credentials never reach the browser (only the redacted URL and
  field names are exposed).

---

## 6. Troubleshooting

| Symptom                            | Fix                                                                                                                    |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| “Demo dataset” badge               | Elasticsearch URL not configured (or `INTEL_DEMO_MODE=on`). Set `INTEL_ELASTICSEARCH_URL`                              |
| “Elasticsearch offline” with a 503 | Check connectivity/credentials; the **Data source** popover shows the raw error                                        |
| Table empty but index has data     | The time field may not be detected. Open **Data source**, then set `INTEL_TIME_FIELD` to your timestamp field          |
| No lines on the map                | Trajectory field not detected or empty. Set `INTEL_TRAJECTORY_FIELD`; check the aircraft has `points` > 0 in the table |
| Map tiles blank                    | Expected in offline mode — the vector basemap is drawn instead. Set `INTEL_MAP_TILE_URL` if you have a tile server     |
| “No local model is available yet”  | Add a model connection in Open WebUI settings (Ollama / OpenAI-compatible)                                             |
| PDF has no text                    | Scanned PDFs need OCR before upload; Open WebUI's extractor returns no text                                            |
| Wrong aircraft de-duplication      | Set `INTEL_ID_FIELD` to a unique per-aircraft key (e.g. `icao24`)                                                      |
