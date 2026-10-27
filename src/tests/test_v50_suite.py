"""
Orunex V50.0 — Full Integration Test Suite
Tests: Intent detection, PPT, Excel/Calendar, PDF, Web search, Config, Code generation
"""
import sys, io, os, time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

# Ensure src/ is always on the path
_this_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir = os.path.abspath(os.path.join(_this_dir, '..'))  # tests/../ = src/
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

out_dir = os.path.abspath(os.path.join(_src_dir, '..', 'orunex_outputs'))
os.makedirs(out_dir, exist_ok=True)

results = {}

print('=' * 60)
print('ORUNEX V50.0 — INTEGRATION TEST SUITE')
print('=' * 60)

# ── T1: Intent Scanner ──────────────────────────────────────────
print('\n[T1] Cerebro Intent Scanner...')
try:
    from agents.cerebro import local_intent_scan
    tests_intent = [
        ('haz una presentacion sobre cambio climatico', 'ppt'),
        ('crea un calendario de mayo 2025', 'excel'),
        ('hazme un pdf sobre inteligencia artificial', 'pdf'),
        ('haz un excel con presupuesto para marketing', 'excel'),
        ('crea una landing page para mi empresa', 'landing'),
        ('haz diapositivas sobre redes neuronales', 'ppt'),
        ('necesito un cronograma semanal', 'excel'),
    ]
    passed = 0
    for prompt, expected_type in tests_intent:
        res = local_intent_scan(prompt)
        ok = res is not None and expected_type in (res or '').lower()
        if ok:
            passed += 1
        status = 'PASS' if ok else 'FAIL'
        print(f'  [{status}] "{prompt[:45]}"')
        print(f'         -> {(res or "None")[:70]}')
    results['T1_Intent'] = f'{passed}/{len(tests_intent)}'
    print(f'  Score: {results["T1_Intent"]}')
except Exception as e:
    print(f'  [FAIL] {e}')
    results['T1_Intent'] = f'FAIL: {e}'

# ── T2: PPT Generator ───────────────────────────────────────────
print('\n[T2] PPT Generator (Professional Dark Theme)...')
try:
    from _orunex_libs.ppt_maker import generate_presentation
    t_start = time.time()
    steps = []
    path = generate_presentation('economia circular y sostenibilidad empresarial',
                                  out_dir, progress_cb=lambda m: steps.append(m))
    elapsed = time.time() - t_start
    if path and os.path.exists(path):
        size_kb = os.path.getsize(path) // 1024
        print(f'  [PASS] {os.path.basename(path)} ({size_kb}KB in {elapsed:.1f}s)')
        print(f'  Progress messages: {len(steps)}')
        for s in steps:
            print(f'    > {s}')
        results['T2_PPT'] = 'PASS'
    else:
        print('  [FAIL] No file generated')
        results['T2_PPT'] = 'FAIL'
except Exception as e:
    import traceback
    traceback.print_exc()
    results['T2_PPT'] = f'FAIL: {e}'

# ── T3: Excel / Calendar ───────────────────────────────────────
print('\n[T3] Excel Generator (Calendar May 2025)...')
try:
    from _orunex_libs.excel_engine import generate_excel
    path = generate_excel('calendario mayo 2025 con tareas semanales de un equipo de marketing', out_dir)
    if path and os.path.exists(path):
        size_kb = os.path.getsize(path) // 1024
        print(f'  [PASS] {os.path.basename(path)} ({size_kb}KB)')
        results['T3_Excel'] = 'PASS'
    else:
        print('  [FAIL] No file generated')
        results['T3_Excel'] = 'FAIL'
except Exception as e:
    print(f'  [FAIL] {e}')
    results['T3_Excel'] = f'FAIL: {e}'

# ── T4: PDF with Web Research ──────────────────────────────────
print('\n[T4] PDF Generator (with real content)...')
try:
    from _orunex_libs.doc_factory import generate_pdf
    path = generate_pdf('estrategias de marketing digital para pymes en 2025', out_dir)
    if path and os.path.exists(path):
        size_kb = os.path.getsize(path) // 1024
        print(f'  [PASS] {os.path.basename(path)} ({size_kb}KB)')
        results['T4_PDF'] = 'PASS'
    else:
        print('  [FAIL] No file generated')
        results['T4_PDF'] = 'FAIL'
except Exception as e:
    print(f'  [FAIL] {e}')
    results['T4_PDF'] = f'FAIL: {e}'

# ── T5: Web Research ───────────────────────────────────────────
print('\n[T5] Headless Web Search...')
try:
    from _orunex_libs.headless_web import search_and_summarize
    t_start = time.time()
    data = search_and_summarize('tendencias inteligencia artificial 2025', max_results=3)
    elapsed = time.time() - t_start
    if data and len(data) > 50:
        print(f'  [PASS] {len(data)} chars in {elapsed:.1f}s')
        print(f'  Sample: {data[:120]}...')
        results['T5_Web'] = 'PASS'
    else:
        print(f'  [FAIL] Too little data: {len(data) if data else 0} chars')
        results['T5_Web'] = 'FAIL'
except Exception as e:
    print(f'  [FAIL] {e}')
    results['T5_Web'] = f'FAIL: {e}'

# ── T6: Config Manager ─────────────────────────────────────────
print('\n[T6] Config Manager (V50 new keys)...')
try:
    from _orunex_libs.config_manager import DEFAULT_CONFIG
    required_keys = ['screen_glow', 'task_timeout_s', 'max_retries', 'copilot_enabled']
    missing = [k for k in required_keys if k not in DEFAULT_CONFIG]
    if not missing:
        for k in required_keys:
            print(f'  {k}: {DEFAULT_CONFIG[k]}')
        results['T6_Config'] = 'PASS'
        print('  [PASS]')
    else:
        print(f'  [FAIL] Missing keys: {missing}')
        results['T6_Config'] = 'FAIL'
except Exception as e:
    print(f'  [FAIL] {e}')
    results['T6_Config'] = f'FAIL: {e}'

# ── T7: Code File Creation ─────────────────────────────────────
print('\n[T7] Code Generation (FILE tag execution)...')
try:
    from _orunex_libs.os_executor import intercept_and_execute
    code = 'print("Orunex V50 - Programming Test OK")\nresult = 2 ** 10\nprint(f"2^10 = {result}")'
    tag = f'[FILE: orunex_test_v50.py]\n{code}\n[/FILE]'
    result_msg = intercept_and_execute(tag)
    expected_path = os.path.join(out_dir, 'orunex_test_v50.py')
    if os.path.exists(expected_path):
        with open(expected_path, 'r') as f:
            content = f.read()
        print(f'  [PASS] File created with {len(content)} chars')
        print(f'  Content preview: {content[:80]}')
        results['T7_Code'] = 'PASS'
    else:
        # Try alternate path
        alt_path = 'orunex_test_v50.py'
        if os.path.exists(alt_path):
            print(f'  [PASS] File created at alternate path')
            results['T7_Code'] = 'PASS'
        else:
            print(f'  [FAIL] File not found. Executor: {result_msg[:100]}')
            results['T7_Code'] = 'FAIL'
except Exception as e:
    import traceback
    traceback.print_exc()
    results['T7_Code'] = f'FAIL: {e}'

# ── T8: Word Generator ─────────────────────────────────────────
print('\n[T8] Word Generator...')
try:
    from _orunex_libs.doc_factory import generate_word
    path = generate_word('informe ejecutivo de resultados de ventas Q1 2025', out_dir)
    if path and os.path.exists(path):
        size_kb = os.path.getsize(path) // 1024
        print(f'  [PASS] {os.path.basename(path)} ({size_kb}KB)')
        results['T8_Word'] = 'PASS'
    else:
        print('  [FAIL] No file generated')
        results['T8_Word'] = 'FAIL'
except Exception as e:
    print(f'  [FAIL] {e}')
    results['T8_Word'] = f'FAIL: {e}'

# ══ SUMMARY ═══════════════════════════════════════════════════
print()
print('=' * 60)
print('FINAL RESULTS:')

def is_strict_pass(v):
    if v == 'PASS': return True
    if isinstance(v, str) and '/' in v and 'FAIL' not in v:
        try:
            num, den = v.split('/')
            return int(num) == int(den) and int(den) > 0
        except: return False
    return False

for k, v in results.items():
    icon = 'PASS' if is_strict_pass(v) else 'FAIL'
    print(f'  [{icon}] {k}: {v}')

strict_pass = sum(1 for v in results.values() if is_strict_pass(v))
print(f'\n  STRICT PASS: {strict_pass}/{len(results)}')
print('=' * 60)

import sys
sys.exit(0 if strict_pass == len(results) else 1)
