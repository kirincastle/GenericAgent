"""
GA Cache — Morphling from headroom v0.26.0 PrefixCacheTracker
==============================================================
重写版: 纯 Python，零外部依赖，只保留核心 cache tracking + 统计。

行为:
- 按 (model, system_prompt_hash) 跟踪每个会话的缓存状态
- 每次请求前: 检查消息结构是否稳定，记录已缓存的消息数
- 每次响应后: 从 usage 读取 cache_read/write 更新状态
- 产出统计日志供 CLI report 使用

与 llmcore.py 集成:
  import ga_cache
  # before send:
  ga_cache.before_request(sess.model, messages)
  # after response:
  ga_cache.after_request(sess.model, usage)
  # periodic report:
  ga_cache.stats()
"""

import json, os, time, hashlib

# ── 本地统计日志 ──────────────────────────────────────
_STATS_DIR = os.path.join(os.path.dirname(__file__) or '.', 'temp', 'ga_cache_stats')
os.makedirs(_STATS_DIR, exist_ok=True)
_STATS_FILE = os.path.join(_STATS_DIR, 'cache_log.jsonl')

# ── 会话跟踪器 ─────────────────────────────────────────
_SESSIONS = {}  # key -> SessionState


def _compute_key(model, system_prompt='', config_overrides=None):
    """会话唯一键: model + system prompt hash."""
    sp_hash = hashlib.sha256((system_prompt or '').encode()).hexdigest()[:12]
    return f"{model}::{sp_hash}"


class SessionState:
    __slots__ = ('model', 'sp_hash', 'system_prompt', 'turns',
                 'total_cache_read', 'total_cache_creation',
                 'total_input_tokens', 'total_output_tokens',
                 'last_cache_read', 'last_cache_creation',
                 'last_input', 'last_output', 'created_at', 'last_seen',
                 'total_compress_before', 'total_compress_after')

    def __init__(self, model, sp_hash, system_prompt):
        self.model = model
        self.sp_hash = sp_hash
        self.system_prompt = system_prompt
        self.turns = 0
        self.total_cache_read = 0
        self.total_cache_creation = 0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.last_cache_read = 0
        self.last_cache_creation = 0
        self.last_input = 0
        self.last_output = 0
        self.created_at = time.time()
        self.last_seen = time.time()
        self.total_compress_before = 0  # 压缩前字符数
        self.total_compress_after = 0   # 压缩后字符数

    @property
    def cache_hit_pct(self):
        total = self.total_cache_read + self.total_cache_creation
        if total == 0:
            return 0.0
        return 100.0 * self.total_cache_read / (self.total_cache_read + self.total_cache_creation)


def _get_session(model, messages=None):
    """获取或创建会话跟踪器."""
    system_prompt = ''
    if messages:
        for m in messages:
            if m.get('role', '').lower() == 'system':
                system_prompt = m.get('content', '') or ''
                break
    key = _compute_key(model, system_prompt)
    if key not in _SESSIONS:
        _SESSIONS[key] = SessionState(model, hashlib.sha256(system_prompt.encode()).hexdigest()[:12], system_prompt)
    return _SESSIONS[key]


def before_request(model, messages):
    """
    请求前调用。
    更新会话状态，记录消息结构 hash 用于稳定性检测。
    """
    sess = _get_session(model, messages)
    sess.last_seen = time.time()

    # 对 DeepSeek 等自动缓存 provider:
    # 早期消息越稳定，缓存命中率越高。
    # 我们确保 system prompt 不变 + 记录消息结构 hash
    msg_struct = _msg_structure(messages)
    _append_log('before', {
        'model': model,
        'turns': sess.turns,
        'msg_count': len(messages),
        'msg_structure': msg_struct,
        'session_age': time.time() - sess.created_at,
    })
    return sess


def after_request(model, usage):
    """
    请求后调用。从 usage 字典取 cache 信息。
    
    DeepSeek/OpenAI 格式:
      usage.prompt_tokens_details.cached_tokens  (cache read)
      usage.prompt_tokens                       (total input)
      usage.completion_tokens                   (output)
    Anthropic 格式:
      usage.cache_creation_input_tokens          (creation)
      usage.cache_read_input_tokens              (read)
      usage.input_tokens
      usage.output_tokens
    """
    if not usage:
        return

    sess = _get_session(model)
    sess.turns += 1

    # 兼容多种格式：
    #   Anthropic: cache_creation_input_tokens / cache_read_input_tokens
    #   OpenAI:    prompt_tokens_details.cached_tokens (cache read, miss inferred)
    #   DeepSeek:  prompt_cache_hit_tokens / prompt_cache_miss_tokens
    ci = usage.get('cache_creation_input_tokens', 0) or \
         usage.get('prompt_cache_miss_tokens', 0) or 0
    cr = usage.get('cache_read_input_tokens', 0) or \
         (usage.get('prompt_tokens_details') or {}).get('cached_tokens', 0) or \
         usage.get('prompt_cache_hit_tokens', 0) or 0
    inp = usage.get('input_tokens', 0) or \
          usage.get('prompt_tokens', 0) or 0
    out = usage.get('completion_tokens', 0) or \
          usage.get('output_tokens', 0) or 0

    sess.last_cache_read = cr
    sess.last_cache_creation = ci
    sess.last_input = inp
    sess.last_output = out

    sess.total_cache_read += cr
    sess.total_cache_creation += ci
    sess.total_input_tokens += inp
    sess.total_output_tokens += out

    _append_log('after', {
        'model': model,
        'turns': sess.turns,
        'cache_read': cr,
        'cache_creation': ci,
        'input_tokens': inp,
        'output_tokens': out,
        'cache_hit_pct': sess.cache_hit_pct,
    })
    return sess


def record_compression(before_chars, after_chars, model=None):
    """记录 SmartCrusher/CodeCompressor 压缩效果."""
    sess = _get_session(model or 'unknown')
    sess.total_compress_before += before_chars
    sess.total_compress_after += after_chars
    _append_log('compress', {
        'model': model or 'unknown',
        'before_chars': before_chars,
        'after_chars': after_chars,
        'saved_chars': before_chars - after_chars,
        'ratio': f"{100.0 * after_chars / before_chars:.1f}%" if before_chars > 0 else "N/A",
    })


def _msg_structure(messages):
    """消息结构 hash — 用于检测前缀是否变化."""
    roles = [m.get('role', '?') for m in messages]
    # 只 hash 前 10 条消息的角色序列 + 各消息长度
    summary = ','.join(roles[:10])
    sizes = [len(json.dumps(m, ensure_ascii=False, default=str)) for m in messages[:10]]
    brief = f"{summary}|{sizes}"
    return hashlib.sha256(brief.encode()).hexdigest()[:8]


def _append_log(event_type, data):
    """追加一条统计日志."""
    try:
        entry = {'t': time.time(), 'event': event_type, **data}
        with open(_STATS_FILE, 'a') as f:
            f.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except Exception:
        pass  # 日志失败不阻塞


def stats():
    """返回所有会话的汇总统计 (dict)."""
    if not _SESSIONS:
        return {'sessions': [], 'total': {}, 'message': 'no data yet'}

    total_cr = sum(s.total_cache_read for s in _SESSIONS.values())
    total_cc = sum(s.total_cache_creation for s in _SESSIONS.values())
    total_inp = sum(s.total_input_tokens for s in _SESSIONS.values())
    total_out = sum(s.total_output_tokens for s in _SESSIONS.values())
    total_turns = sum(s.turns for s in _SESSIONS.values())

    overall_hit = 100.0 * total_cr / (total_cr + total_cc) if (total_cr + total_cc) > 0 else 0.0
    total_saved = sum(s.total_compress_before - s.total_compress_after for s in _SESSIONS.values())

    session_list = []
    for key, s in sorted(_SESSIONS.items(), key=lambda x: -x[1].total_cache_read):
        compress_ratio = f"{100.0 * s.total_compress_after / s.total_compress_before:.1f}%" if s.total_compress_before > 0 else "-"
        session_list.append({
            'model': s.model,
            'turns': s.turns,
            'cache_hit_pct': round(s.cache_hit_pct, 1),
            'total_cache_read': s.total_cache_read,
            'total_cache_creation': s.total_cache_creation,
            'total_input': s.total_input_tokens,
            'total_output': s.total_output_tokens,
            'compress_before': s.total_compress_before,
            'compress_after': s.total_compress_after,
            'compress_ratio': compress_ratio,
            'created': time.strftime('%H:%M:%S', time.localtime(s.created_at)),
            'idle': f"{(time.time() - s.last_seen) / 60:.0f}m" if s.last_seen > 0 else '-',
        })

    return {
        'sessions': session_list,
        'total': {
            'sessions': len(_SESSIONS),
            'total_turns': total_turns,
            'overall_cache_hit_pct': round(overall_hit, 1),
            'total_cache_read': total_cr,
            'total_cache_creation': total_cc,
            'total_input_tokens': total_inp,
            'total_output_tokens': total_out,
            'total_compress_saved_chars': total_saved,
        }
    }


def report(text_only=False):
    """打印统计报告 (CLI)."""
    data = stats()
    total = data['total']
    sessions = data['sessions']

    lines = []
    lines.append('═' * 60)
    lines.append('  GA Cache 统计报告')
    lines.append('═' * 60)
    lines.append(f"  会话数:        {total.get('sessions', 0)}")
    lines.append(f"  总轮数:        {total.get('total_turns', 0)}")
    lines.append(f"  Cache 命中率:  {total.get('overall_cache_hit_pct', 0)}%")
    lines.append(f"  Cache Read:    {total.get('total_cache_read', 0)} tokens")
    lines.append(f"  Cache Create:  {total.get('total_cache_creation', 0)} tokens")
    lines.append(f"  输入节省:      {total.get('total_compress_saved_chars', 0)} chars")
    lines.append('─' * 60)

    if sessions:
        lines.append(f"  {'模型':<28} {'轮数':>4} {'Hit%':>5} {'Read':>8} {'Create':>8}")
        lines.append('─' * 60)
        for s in sessions:
            model_short = s['model'][:28]
            lines.append(f"  {model_short:<28} {s['turns']:>4} {s['cache_hit_pct']:>4}% "
                         f"{s['total_cache_read']:>8} {s['total_cache_creation']:>8}")
        lines.append('─' * 60)

    lines.append(f"  ⏳ 上次 {time.strftime('%H:%M:%S')}")
    lines.append('═' * 60)
    result = '\n'.join(lines)

    if not text_only:
        print(result)
    return result


def reset(model=None):
    """重置跟踪状态."""
    global _SESSIONS
    if model:
        _SESSIONS = {k: v for k, v in _SESSIONS.items() if model not in k}
    else:
        _SESSIONS = {}
        # 也清空日志
        try:
            if os.path.exists(_STATS_FILE):
                os.remove(_STATS_FILE)
        except Exception:
            pass


if __name__ == '__main__':
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == 'reset':
        reset()
        print('[ga_cache] Reset all sessions.')
    else:
        report()
