#!/usr/bin/env node
/**
 * Standalone database seeder for agent-session-search.
 * Creates the SQLite database and indexes local sessions, so the MCP server
 * (and future Electron GUI) can use it without ever launching the GUI.
 *
 * Run: node seed-session-search-db.mjs
 * Reads pointer file: ~/.agent-session-search/db-path
 * Override: env AGENT_SESSION_SEARCH_DB
 */

import { existsSync, mkdirSync, readFileSync, writeFileSync, readdirSync, statSync, lstatSync } from "node:fs";
import { homedir } from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";

const home = homedir();
const pointerDir = path.join(home, ".agent-session-search");
const pointerFile = path.join(pointerDir, "db-path");

// Resolve DB path (same logic as app-paths.ts)
function resolveDbPath() {
  const override = process.env.AGENT_SESSION_SEARCH_DB?.trim();
  if (override) return override;
  try {
    if (!existsSync(pointerFile)) return null;
    const val = readFileSync(pointerFile, "utf8").trim();
    return val || null;
  } catch {
    return null;
  }
}

// Default: write to a stable location
const DB_PATH = resolveDbPath() || path.join(home, ".agent-session-search", "sessions.sqlite");

console.log(`DB path: ${DB_PATH}`);

mkdirSync(path.dirname(DB_PATH), { recursive: true });
mkdirSync(pointerDir, { recursive: true });
writeFileSync(pointerFile, `${DB_PATH}\n`, "utf8");

const db = new DatabaseSync(DB_PATH);
initializeSchema(db);

// --- Index all sessions ---
console.log("Indexing sessions...");

const codexDir = path.join(home, ".codex");
const claudeDir = path.join(home, ".claude");

// Walk JSONL files (with symlink dir support, like the patched walkJsonlFiles)
function walkJsonlFiles(dir) {
  let entries = [];
  try {
    entries = readdirSync(dir, { withFileTypes: true });
  } catch {
    return [];
  }
  const files = [];
  for (const entry of entries) {
    const fullPath = path.join(dir, entry.name);
    if (entry.isDirectory() || (entry.isSymbolicLink() && statSync(fullPath).isDirectory())) {
      files.push(...walkJsonlFiles(fullPath));
    } else if (entry.name.endsWith(".jsonl")) {
      files.push(fullPath);
    }
  }
  return files;
}

// Read title index
const titleMap = new Map();
const indexPath = path.join(codexDir, "session_index.jsonl");
if (existsSync(indexPath)) {
  for (const line of readFileSync(indexPath, "utf8").trim().split("\n").filter(Boolean)) {
    try {
      const row = JSON.parse(line);
      if (row.id && row.thread_name) titleMap.set(row.id, { title: row.thread_name, updatedAt: row.updated_at || "" });
    } catch {}
  }
}

// Load Codex sessions from ~/.codex/sessions
const sessionsDir = path.join(codexDir, "sessions");
let totalIndexed = 0;

if (existsSync(sessionsDir)) {
  for (const filePath of walkJsonlFiles(sessionsDir)) {
    try {
      const rows = readJsonl(filePath);
      if (rows.length === 0) continue;
      const meta = parseCodexMeta(rows[0]);
      if (!meta) continue;
      const idx = titleMap.get(meta.id);
      indexSession(db, {
        filePath,
        rows,
        keyPrefix: "codex",
        source: meta.originator === "Codex Desktop" ? "codex-app" : "codex-cli",
        rawId: meta.id,
        projectPath: meta.cwd || "",
        originalTitle: idx?.title || meta.title || "",
        timestamp: meta.ts ? new Date(meta.ts).getTime() : 0,
      });
      totalIndexed++;
    } catch (e) {
      // skip corrupt files
    }
  }
}

// Load Claude CLI sessions from ~/.claude/projects/*/*.jsonl
const claudeProjects = path.join(claudeDir, "projects");
if (existsSync(claudeProjects)) {
  for (const projectDir of readdirSync(claudeProjects, { withFileTypes: true })) {
    if (!projectDir.isDirectory()) continue;
    const projPath = path.join(claudeProjects, projectDir.name);
    for (const file of readdirSync(projPath)) {
      if (!file.endsWith(".jsonl")) continue;
      try {
        const filePath = path.join(projPath, file);
        const rows = readJsonl(filePath);
        if (rows.length === 0) continue;
        // Claude JSONL format
        const cwd = extractClaudeCwd(rows);
        const title = extractClaudeTitle(rows);
        const ts = extractClaudeTimestamp(rows);
        const rawId = path.basename(file, ".jsonl");
        indexSession(db, {
          filePath,
          rows,
          keyPrefix: "claude",
          source: "claude-cli",
          rawId,
          projectPath: cwd || "",
          originalTitle: title || "",
          timestamp: ts,
        });
        totalIndexed++;
      } catch {}
    }
  }
}

// Load GA sessions from ga_import symlink
const gaDir = path.join(codexDir, "sessions", "ga_import");
if (existsSync(gaDir)) {
  for (const file of readdirSync(gaDir)) {
    if (!file.endsWith(".jsonl")) continue;
    try {
      const filePath = path.join(gaDir, file);
      const rows = readJsonl(filePath);
      if (rows.length === 0) continue;
      const meta = parseCodexMeta(rows[0]);
      if (!meta) continue;
      indexSession(db, {
        filePath,
        rows,
        keyPrefix: "codex",
        source: "codex-cli",
        rawId: meta.id,
        projectPath: meta.cwd || "",
        originalTitle: meta.title || "",
        timestamp: meta.ts ? new Date(meta.ts).getTime() : 0,
      });
      totalIndexed++;
    } catch {}
  }
}

console.log(`\nTotal sessions indexed: ${totalIndexed}`);
db.close();
console.log("Database ready.");

// --- Helper functions ---

function initializeSchema(db) {
  db.exec("PRAGMA foreign_keys = ON");
  try { db.exec("PRAGMA journal_mode = WAL"); } catch {}
  db.exec(`
    CREATE TABLE IF NOT EXISTS sessions (
      session_key TEXT PRIMARY KEY,
      raw_id TEXT NOT NULL,
      source TEXT NOT NULL,
      environment_id TEXT NOT NULL DEFAULT 'local',
      project_path TEXT NOT NULL,
      file_path TEXT NOT NULL,
      original_title TEXT NOT NULL,
      first_question TEXT NOT NULL,
      timestamp INTEGER NOT NULL,
      file_mtime_ms REAL NOT NULL DEFAULT 0,
      file_size INTEGER NOT NULL DEFAULT 0,
      custom_title TEXT,
      favorited INTEGER NOT NULL DEFAULT 0,
      pinned INTEGER NOT NULL DEFAULT 0,
      hidden INTEGER NOT NULL DEFAULT 0,
      last_opened_at INTEGER,
      message_count INTEGER NOT NULL DEFAULT 0,
      input_tokens INTEGER NOT NULL DEFAULT 0,
      output_tokens INTEGER NOT NULL DEFAULT 0,
      cached_input_tokens INTEGER NOT NULL DEFAULT 0,
      reasoning_output_tokens INTEGER NOT NULL DEFAULT 0,
      total_tokens INTEGER NOT NULL DEFAULT 0,
      indexed_at INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS messages (
      session_key TEXT NOT NULL,
      message_index INTEGER NOT NULL,
      role TEXT NOT NULL,
      content TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      PRIMARY KEY (session_key, message_index),
      FOREIGN KEY (session_key) REFERENCES sessions(session_key) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS token_events (
      session_key TEXT NOT NULL,
      dedupe_key TEXT NOT NULL,
      timestamp INTEGER NOT NULL,
      input_tokens INTEGER NOT NULL DEFAULT 0,
      output_tokens INTEGER NOT NULL DEFAULT 0,
      cached_input_tokens INTEGER NOT NULL DEFAULT 0,
      reasoning_output_tokens INTEGER NOT NULL DEFAULT 0,
      total_tokens INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY (session_key, dedupe_key),
      FOREIGN KEY (session_key) REFERENCES sessions(session_key) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS trace_events (
      session_key TEXT NOT NULL,
      trace_index INTEGER NOT NULL,
      kind TEXT NOT NULL,
      source TEXT NOT NULL,
      title TEXT NOT NULL,
      detail TEXT NOT NULL,
      timestamp TEXT NOT NULL,
      call_id TEXT,
      event_type TEXT,
      status TEXT,
      PRIMARY KEY (session_key, trace_index),
      FOREIGN KEY (session_key) REFERENCES sessions(session_key) ON DELETE CASCADE
    );
    CREATE VIRTUAL TABLE IF NOT EXISTS session_fts USING fts5(
      session_key UNINDEXED,
      title,
      first_question,
      content_text,
      project_path,
      tokenize = 'unicode61'
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_source ON sessions(source);
    CREATE INDEX IF NOT EXISTS idx_sessions_project_path ON sessions(project_path);
    CREATE INDEX IF NOT EXISTS idx_sessions_hidden_favorited_pinned ON sessions(hidden, favorited, pinned);
    CREATE INDEX IF NOT EXISTS idx_sessions_environment ON sessions(environment_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_environment_source ON sessions(environment_id, source);
    CREATE INDEX IF NOT EXISTS idx_token_events_timestamp ON token_events(timestamp);
    CREATE INDEX IF NOT EXISTS idx_trace_events_session ON trace_events(session_key, trace_index);
  `);
}

function readJsonl(filePath) {
  const text = readFileSync(filePath, "utf8");
  return text.trim().split("\n").filter(Boolean).map(line => {
    try { return JSON.parse(line); } catch { return null; }
  }).filter(Boolean);
}

function parseCodexMeta(line) {
  if (!line || typeof line !== "object") return null;
  const l = line;
  if (l.type === "session_meta" && l.payload?.id) {
    return {
      id: l.payload.id,
      cwd: l.payload.cwd || "",
      ts: l.timestamp || "",
      title: l.payload.title || "",
      originator: l.payload.originator || "",
    };
  }
  return null;
}

function extractClaudeCwd(rows) {
  for (const row of rows) {
    if (row && typeof row === "object" && row.cwd && typeof row.cwd === "string" && row.cwd.startsWith("/")) return row.cwd;
    if (row && typeof row === "object" && row.type === "last-prompt") continue;
  }
  return "";
}

function extractClaudeTitle(rows) {
  for (const row of rows) {
    if (row && typeof row === "object" && row.type === "user" && row.message?.content) {
      const text = (Array.isArray(row.message.content) ? row.message.content.map(c => c.text || "").join(" ") : row.message.content).trim();
      if (text && text.length > 3 && text.length < 200) return text;
    }
  }
  return "";
}

function extractClaudeTimestamp(rows) {
  for (const row of rows) {
    if (row && typeof row === "object" && row.timestamp) {
      return new Date(row.timestamp).getTime();
    }
  }
  return 0;
}

function indexSession(db, { filePath, rows, keyPrefix, source, rawId, projectPath, originalTitle, timestamp }) {
  const fileStat = statSync(filePath);
  const sessionKey = `${keyPrefix}:${rawId}`;
  const now = Date.now();

  // Extract user messages for content
  const messages = [];
  let firstQuestion = "";

  for (const row of rows) {
    if (typeof row !== "object" || !row) continue;
    // Codex format
    if (row.type === "response_item" && row.payload?.type === "message" && row.payload.role) {
      const role = row.payload.role;
      if (role !== "user" && role !== "assistant") continue;
      let text = "";
      if (Array.isArray(row.payload.content)) {
        text = row.payload.content
          .filter(c => c && typeof c === "object" && c.type !== "tool_use" && c.type !== "tool_result" && c.type !== "thinking" && c.type !== "input_image")
          .map(c => c.text || "")
          .join("\n")
          .trim();
      }
      if (text) {
        messages.push({ role, content: text, timestamp: row.timestamp || "" });
        if (!firstQuestion && role === "user") firstQuestion = text.slice(0, 500);
      }
    }
    // Claude format
    else if (row.type === "user" && row.message?.content || row.type === "assistant" && row.message?.content) {
      const role = row.type;
      const content = row.message.content;
      let text = "";
      if (Array.isArray(content)) {
        text = content.map(c => c.text || "").join("\n").trim();
      } else if (typeof content === "string") {
        text = content.trim();
      }
      if (text) {
        messages.push({ role, content: text, timestamp: row.timestamp || "" });
        if (!firstQuestion && role === "user") firstQuestion = text.slice(0, 500);
      }
    }
  }

  const title = originalTitle || firstQuestion.slice(0, 100) || "Untitled Session";
  const contentText = messages.map(m => m.content).join("\n\n").slice(0, 100000);

  const insertSession = db.prepare(`
    INSERT OR REPLACE INTO sessions
      (session_key, raw_id, source, environment_id, project_path, file_path,
       original_title, first_question, timestamp, file_mtime_ms, file_size,
       message_count, indexed_at)
    VALUES (?, ?, ?, 'local', ?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);

  insertSession.run(
    sessionKey, rawId, source, projectPath, filePath,
    title, firstQuestion, timestamp, fileStat.mtimeMs, fileStat.size,
    messages.length, now,
  );

  // Insert messages
  const msgStmt = db.prepare(`
    INSERT OR REPLACE INTO messages (session_key, message_index, role, content, timestamp)
    VALUES (?, ?, ?, ?, ?)
  `);

  for (let i = 0; i < messages.length; i++) {
    msgStmt.run(sessionKey, i, messages[i].role, messages[i].content, messages[i].timestamp);
  }

  // FTS
  try {
    const ftsStmt = db.prepare(`
      INSERT OR REPLACE INTO session_fts (session_key, title, first_question, content_text, project_path)
      VALUES (?, ?, ?, ?, ?)
    `);
    ftsStmt.run(sessionKey, title, firstQuestion, contentText, projectPath);
  } catch {}
}
