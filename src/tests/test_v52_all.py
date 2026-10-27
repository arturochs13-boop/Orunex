import sys, io, os, time, json, re, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

_src_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _src_dir not in sys.path: sys.path.insert(0, _src_dir)

print('=' * 60)
print('ORUNEX V52.0 - 5 ARCHITECTURAL ENHANCEMENTS VERIFICATION')
print('=' * 60)

# 1. DAG Parallel Batching Test
print('\n[FEATURE 1] DAG Parallel Batching Engine...')
t0 = time.time()
try:
    from _orunex_libs import project_manager
    project_manager.ACTIVE_PROJECT = None
    steps = [
        {'title': 'Gen PDF', 'desc': '[MAKE_DOC: pdf | report]'},
        {'title': 'Gen Excel', 'desc': '[MAKE_DOC: excel | data]'},
        {'title': 'Use Both', 'desc': 'Unir los datos del archivo anterior'}
    ]
    project_manager.start_project('DAG Parallel Test', steps)
    batch = project_manager.ACTIVE_PROJECT.get_parallel_batch()
    batch_titles = [s.title for s in batch]
    ok_batch = (len(batch) == 2 and 'Gen PDF' in batch_titles and 'Gen Excel' in batch_titles)
    print(f'  Parallel batch detected ({len(batch)} steps): {batch_titles}')
    print('  [PASS]' if ok_batch else '  [FAIL]')
    project_manager.ACTIVE_PROJECT = None
except Exception as e:
    print('  [FAIL] Exception:', e)

# 2. Token Streaming Test
print('\n[FEATURE 2] Real-Time Token Streaming Engine...')
t0 = time.time()
try:
    from _orunex_libs.ollama_client import call_ollama_stream
    tokens = []
    def on_token(t): tokens.append(t)
    res = call_ollama_stream('orunex_v37', 'Dime hola en tres palabras', callback=on_token, options={'temperature': 0.1})
    ok_stream = len(tokens) > 0 and len(res.get('response', '')) > 0
    print(f'  Tokens received in real-time stream: {len(tokens)}')
    print('  [PASS]' if ok_stream else '  [FAIL]')
except Exception as e:
    print('  [FAIL] Exception:', e)

# 3. Fast-Healer Layer 1 Test
print('\n[FEATURE 3] Fast-Healer Sub-50ms Deterministic Repair...')
t0 = time.time()
try:
    from _orunex_libs.auto_healer import heuristic_heal
    
    cmd_broken = 'python3 script/test.py'
    err_msg = 'python3: command not found'
    t_h = time.time()
    fixed = heuristic_heal(cmd_broken, err_msg)
    h_time_ms = (time.time() - t_h) * 1000
    
    ok_healer = fixed == 'python script\\test.py' and h_time_ms < 50
    print(f'  Repaired in {h_time_ms:.2f}ms: "{cmd_broken}" -> "{fixed}"')
    print('  [PASS]' if ok_healer else '  [FAIL]')
except Exception as e:
    print('  [FAIL] Exception:', e)

# 4. Synapse Memory RAG Test
print('\n[FEATURE 4] Synapse Vector RAG Memory Search...')
t0 = time.time()
try:
    from _orunex_libs import project_manager
    project_manager.ACTIVE_PROJECT = None
    project_manager.start_project('RAG Memory Test', [
        {'title': 'Criptomonedas', 'desc': 'investigar bitcoin'},
        {'title': 'Energia Solar', 'desc': 'investigar paneles'},
        {'title': 'Informe Final', 'desc': 'redactar resumen'}
    ])
    
    # Simulate step completions with vector embeddings
    project_manager.mark_step_success('[HEADLESS_SEARCH done] Bitcoin alcanzó los ,000 USD en 2025.')
    project_manager.mark_step_success('[HEADLESS_SEARCH done] Paneles solares aumentan su eficiencia 40%.')
    
    rag_res = project_manager.search_memory_rag('precios de bitcoin', top_k=1)
    ok_rag = len(rag_res) > 0 and 'Bitcoin' in rag_res[0]['text']
    if ok_rag:
        print(f'  RAG retrieved top match: [{rag_res[0]["title"]}] -> {rag_res[0]["text"][:60]}')
    print('  [PASS]' if ok_rag else '  [FAIL]')
    project_manager.ACTIVE_PROJECT = None
except Exception as e:
    print('  [FAIL] Exception:', e)

# 5. GUI Vision Grounding Test
print('\n[FEATURE 5] GUI Vision Grounding Bounds Calculation...')
t0 = time.time()
try:
    from _orunex_libs.os_executor import get_active_window_element_bounds
    bounds = get_active_window_element_bounds('centro de pantalla')
    ok_bounds = bounds is not None and isinstance(bounds, tuple) and len(bounds) == 2
    print(f'  Win32 Active Window Bounds center: {bounds}')
    print('  [PASS]' if ok_bounds else '  [FAIL]')
except Exception as e:
    print('  [FAIL] Exception:', e)

print('\n' + '=' * 60)
print('ORUNEX V52.0 VERIFICATION COMPLETE')
print('=' * 60)
