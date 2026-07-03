# SOP: `/fk` — GA Feedback Processing

## Location

Feedback server & store: `/home/moclaw/projects/external/genericagent/ga-feedback/`

## Standard Flow

```
/fk → check pending? → (if >0) read all → apply changes → ack → report
```

### Step-by-step

1. **Check for unread feedback**
   ```
   curl -s http://localhost:9876/api/pending
   ```

2. **If pending > 0, fetch all feedbacks**
   ```
   curl -s http://localhost:9876/api/feedbacks
   ```
   Returns JSON array. Each entry contains `feedbacks` array with items like:
   `{"xpath": "...", "text": "...", "note": "..."}`, plus `url` and `title`.

3. **Read each pending feedback** (after last ack'd index, tracked in `last_read.txt`)
   - Understand the user's note/comment from the feedback
   - Apply the requested code changes
   - Verify with build/tests if applicable

4. **Acknowledge processed feedbacks**
   ```
   curl -s "http://localhost:9876/api/ack?count=N"
   ```
   where N = new last_read index (total feedbacks processed so far).

5. **Report** to the user: what was found, what was fixed, what remains.

## Fallback (when server is unreachable)

The sandbox environment may prevent listening on port 9876. In that case, read the feedback store directly:

```sh
cd /home/moclaw/projects/external/genericagent/ga-feedback
python3 -c "import json; data=json.load(open('feedbacks.json')); print(json.dumps(data[int(open('last_read.txt').read().strip()):], indent=2, ensure_ascii=False))"
```

To ack without the server, write the new index to `last_read.txt`:

```sh
echo '<new_count>' > /home/moclaw/projects/external/genericagent/ga-feedback/last_read.txt
```

## Files

| File | Purpose |
|------|---------|
| `feedbacks.json` | All feedbacks (append-only) |
| `last_read.txt` | Index of last processed feedback (0-based) |
| `server.py` | HTTP server (optional, port 9876) |
| `www/` | Static files for bookmarklet UI |

## Pre-approved Commands

The following operations are pre-approved (no approval needed):

- `curl -s http://localhost:9876/api/pending`
- `curl -s http://localhost:9876/api/feedbacks`
- `curl -s "http://localhost:9876/api/ack?count=*"`
- `curl -s http://localhost:9876/api/health`
- Starting/restarting the GA feedback server
