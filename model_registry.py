"""
model_registry — 从 models.dev/api.json 获取模型规格，自动校正 context_win。

用法:
    from model_registry import lookup_model, auto_fix_config, get_registry

    # 查模型
    spec = lookup_model('deepseek-v4-flash-free')
    if spec: print(spec['context'])  # 200000

    # 自动校正 config dict
    cfg = {'model': 'deepseek-v4-flash-free', 'context_win': 70000}
    auto_fix_config(cfg, verbose=True)
    # cfg['context_win'] → 400000

    # CLI
    python model_registry.py --refresh    # 刷新缓存并检查 mykey.py
    python model_registry.py --show       # 显示所有已知模型
    python model_registry.py --check-cfg mykey.py  # 检查指定配置文件
"""

import json, os, sys, time, re
from datetime import datetime

MODELS_API_URL = 'https://models.dev/api.json'
ROOT = os.path.dirname(os.path.abspath(__file__))
CACHE_FILE = os.path.join(ROOT, 'temp', 'model_registry_cache.json')
CACHE_TTL = 86400  # 24 小时

# cost() 用 json.dumps 算字符数，模型 specs 用 tokens
# 混合内容 (英文+中文) 保守比例 ≈ 4 chars/token
# context_win → cap = context_win * 2, 我们想要 cap ≈ context_tokens * 4
# 所以 context_win = context_tokens * 2
CHARS_PER_TOKEN = 4.0
CONTEXT_WIN_FACTOR = CHARS_PER_TOKEN / 2.0  # = 2.0


# ─── 缓存管理 ────────────────────────────────────────────────────────

def _cache_path():
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    return CACHE_FILE


def _load_cache():
    """读取缓存，过期返回 None。"""
    p = _cache_path()
    if not os.path.exists(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if time.time() - data.get('_fetched_at', 0) > CACHE_TTL:
            return None  # 过期
        return data
    except (json.JSONDecodeError, OSError):
        return None


def _save_cache(data):
    """写入缓存。"""
    data['_fetched_at'] = time.time()
    data['_cached_at'] = datetime.now().isoformat()
    p = _cache_path()
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ─── API 交互 ────────────────────────────────────────────────────────

def _fetch_registry():
    """从 API 拉取完整 registry。"""
    try:
        import requests
        r = requests.get(MODELS_API_URL, timeout=15)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f'[model_registry] Failed to fetch {MODELS_API_URL}: {e}')
        return None


def _build_index(data):
    """将嵌套的 provider → models 结构拍平成 model_id → spec 的索引。"""
    index = {}
    for provider, pdata in data.items():
        if not isinstance(pdata, dict):
            continue  # 跳过非 dict 条目（如数值、列表）
        models = pdata.get('models', {})
        for model_id, minfo in models.items():
            name = minfo.get('name', model_id)
            limit = minfo.get('limit') or {}
            cost = minfo.get('cost') or {}
            spec = {
                'name': name,
                'provider': provider,
                'context': limit.get('context', 0),
                'output': limit.get('output', 0),
                'cost_input': cost.get('input', 0),
                'cost_output': cost.get('output', 0),
                'cost_cache_read': cost.get('cache_read', 0),
                'reasoning': minfo.get('reasoning', False),
                'tool_call': minfo.get('tool_call', False),
                'knowledge': minfo.get('knowledge', ''),
                'release_date': minfo.get('release_date', ''),
            }
            # 同时用 model_id 和 name 索引
            index[model_id] = spec
            index[name] = spec  # name 可能覆盖，但同一个 spec 对象没问题
    return index


# ─── 公开 API ────────────────────────────────────────────────────────

def get_registry(force_refresh=False, no_fetch=False):
    """
    获取模型 registry（带缓存）。

    Args:
        force_refresh: 强制重新拉取
        no_fetch: 仅用缓存，不发起网络请求

    Returns:
        dict[model_id → spec]
    """
    data = None

    if not force_refresh:
        data = _load_cache()

    if data is None and not no_fetch:
        data = _fetch_registry()

    if data is None:
        # 最后手段：用过期的缓存
        p = _cache_path()
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                print(f'[model_registry] Using stale cache from {data.get("_cached_at", "unknown")}')
            except Exception:
                pass

    if data is None:
        return {}

    # 写缓存（仅当是新鲜数据）
    if not no_fetch and data.get('_fetched_at', 0) > time.time() - 60:
        _save_cache(data)

    return _build_index(data)


def lookup_model(model_name, registry=None, fuzzy=True):
    """
    按名称查找模型 spec。

    Args:
        model_name: 模型名称或 ID
        registry: 预加载的 registry（可选，自动获取）
        fuzzy: 是否模糊匹配（默认 True）

    Returns:
        spec dict 或 None
    """
    if not model_name:
        return None
    if registry is None:
        registry = get_registry()

    # 精确匹配
    if model_name in registry:
        return registry[model_name]

    if not fuzzy:
        return None

    model_lower = model_name.lower().strip()

    # 大小写不敏感
    for mid, spec in registry.items():
        if model_lower == mid.lower():
            return spec
        if model_lower == spec.get('name', '').lower():
            return spec

    # 子串匹配：config 里可能有前缀如 "opf-1/deepseek-v4-flash-free"
    candidates = []
    for mid, spec in registry.items():
        mid_lower = mid.lower()
        spec_name = spec.get('name', '').lower()
        # 完整容器匹配（不拆前缀）
        if mid_lower in model_lower or model_lower in mid_lower or spec_name in model_lower or model_lower in spec_name:
            candidates.append((len(mid_lower), mid, spec))  # 更长 id 优先
    # 按匹配长度降序，避免 "deepseek-v4-flash" 吃掉 "deepseek-v4-flash-free"
    candidates.sort(key=lambda x: -x[0])
    if candidates:
        return candidates[0][2]

    return None


def calc_context_win(context_tokens):
    """
    将 token 数转换为 context_win（字符单位）。

    cost() = len(json.dumps(messages)) → chars
    cap = context_win * 2
    目标: cap ≈ context_tokens * CHARS_PER_TOKEN
    所以: context_win = context_tokens * CHARS_PER_TOKEN / 2
                      = context_tokens * CONTEXT_WIN_FACTOR
    """
    return int(context_tokens * CONTEXT_WIN_FACTOR)


def auto_fix_config(cfg, verbose=True, registry=None):
    """
    根据 model 字段自动校正 config 的 context_win。

    Args:
        cfg: config 字典，必须有 'model' 键
        verbose: 是否打印变更信息
        registry: 预加载的 registry

    Returns:
        (changed, model_name, expected, old_val):
        changed: 是否做了更正
        model_name: 模型名称
        expected: 计算出的正确 context_win
        old_val: 原来的 context_win
    """
    model = cfg.get('model', '')
    if not model:
        return False, '', 0, 0

    if registry is None:
        registry = get_registry(no_fetch=True)
        if not registry:
            # 没有缓存，静默尝试拉取
            registry = get_registry()

    spec = lookup_model(model, registry)
    if spec is None:
        if verbose:
            print(f'[model_registry] ⚠ Unknown model: {model!r}')
        return False, model, 0, 0

    ctx_tokens = spec.get('context', 0)
    if ctx_tokens <= 0:
        return False, model, 0, 0

    expected = calc_context_win(ctx_tokens)
    old_val = cfg.get('context_win', 0)

    if old_val == expected:
        return False, model, expected, old_val

    # 执行校正
    cfg['context_win'] = expected
    # 同时修正 model name 为规范名称（可选）
    # cfg['model'] = spec['name']

    if verbose:
        pct = abs(expected - old_val) / max(expected, old_val) * 100
        direction = '↑' if expected > old_val else '↓'
        print(f'[model_registry] ✏ {model}: context_win {old_val}→{expected} '
              f'{direction}{pct:.0f}% ({ctx_tokens} tokens @ {CHARS_PER_TOKEN} chars/token)')

    return True, model, expected, old_val


def check_mykey_configs(path=None, verbose=True):
    """
    检查 mykey.py（或任意配置文件）中所有 config 的 context_win。

    Args:
        path: 文件路径，默认 ../mykey.py
        verbose: 打印结果

    Returns:
        [(model, old, expected, corrected), ...]
    """
    if path is None:
        path = os.path.join(ROOT, 'mykey.py')

    # 动态导入
    sys.path.insert(0, os.path.dirname(path))
    try:
        import importlib
        import mykey
        importlib.reload(mykey)
    except Exception as e:
        print(f'[model_registry] Failed to import mykey: {e}')
        return []

    registry = get_registry()
    results = []

    for key, val in vars(mykey).items():
        if key.startswith('_'):
            continue
        if isinstance(val, dict) and 'model' in val and 'context_win' in val:
            old = val.get('context_win', 0)
            changed, model, expected, old_val = auto_fix_config(val, verbose=verbose, registry=registry)
            if changed:
                results.append((model, old_val, expected, True))
            elif verbose:
                spec = lookup_model(model, registry)
                if spec and old != expected:
                    results.append((model, old, expected, False))

    return results


# ─── CLI ─────────────────────────────────────────────────────────────

def _cmd_refresh():
    """强制刷新缓存。"""
    print('[model_registry] Refreshing model registry...')
    data = _fetch_registry()
    if data:
        _save_cache(data)
        idx = _build_index(data)
        print(f'[model_registry] ✓ Cached {len(idx)} models from {len(data)} providers')
        # 检查 mykey.py
        print()
        check_mykey_configs()
    else:
        print('[model_registry] ✗ Failed to fetch registry')
        return 1
    return 0


def _cmd_show(filter_str=None):
    """显示所有已知模型。"""
    registry = get_registry()
    seen = set()
    models = []
    for mid, spec in registry.items():
        if mid in seen:
            continue
        if filter_str and filter_str.lower() not in mid.lower() and filter_str.lower() not in spec.get('name', '').lower():
            continue
        models.append((mid, spec))
        seen.add(mid)

    if not models:
        print('[model_registry] No models found' + (f' matching {filter_str!r}' if filter_str else ''))
        return

    models.sort(key=lambda x: x[0])
    print("{:40s} {:30s} {:>10s} {:>10s}  {:20s}  {:10s}".format("Model ID", "Name", "Context", "Output", "Cost I/O/Cache", "Reasoning"))
    print('-' * 130)
    for mid, spec in models:
        ctx = str(spec['context']) if spec['context'] else '-'
        out = str(spec['output']) if spec['output'] else '-'
        ci, co, cc = spec['cost_input'], spec['cost_output'], spec['cost_cache_read']
        cost_str = f'{ci}/{co}/{cc}'
        rsn = 'Y' if spec['reasoning'] else 'N'
        print("{:40s} {:30s} {:>10s} {:>10s}  {:20s}  {:10s}".format(mid, spec["name"], ctx, out, cost_str, rsn))


def _cmd_check_cfg(path):
    """检查配置文件的 context_win。"""
    results = check_mykey_configs(path)
    if not results:
        print('[model_registry] ✓ All configs are correct')
    else:
        for model, old, expected, corrected in results:
            status = '✓ CORRECTED' if corrected else '✗ MISMATCH'
            print(f'  {status}: {model} context_win={old} should be {expected}')


if __name__ == '__main__':
    if '--refresh' in sys.argv:
        sys.exit(_cmd_refresh())
    elif '--show' in sys.argv:
        filter_str = None
        for i, a in enumerate(sys.argv):
            if a == '--show' and i + 1 < len(sys.argv) and not sys.argv[i+1].startswith('--'):
                filter_str = sys.argv[i+1]
                break
        _cmd_show(filter_str)
    elif '--check-cfg' in sys.argv:
        idx = sys.argv.index('--check-cfg')
        path = sys.argv[idx + 1] if idx + 1 < len(sys.argv) else None
        _cmd_check_cfg(path)
    else:
        _cmd_show()
