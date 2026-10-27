import sys, io, os, time, json, re, traceback
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
_this_dir = os.path.dirname(os.path.abspath(__file__))
_src_dir  = os.path.abspath(os.path.join(_this_dir, '..'))
if _src_dir not in sys.path: sys.path.insert(0, _src_dir)
OUT_DIR = os.path.abspath(os.path.join(_src_dir, '..', 'orunex_outputs'))
os.makedirs(OUT_DIR, exist_ok=True)
REPORT = {'suite': 'Autonomy V51', 'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'), 'tests': []}
DIVIDER = '=' * 60

def record(name, status, details, elapsed=None, fixes=None):
    entry = {'name': name, 'status': status, 'details': details}
    if elapsed is not None: entry['elapsed_s'] = round(elapsed, 2)
    if fixes: entry['improvement_needed'] = fixes
    REPORT['tests'].append(entry)
    icon = 'PASS' if status == 'PASS' else 'FAIL' if status == 'FAIL' else 'WARN'
    print(f'  [{icon}] {name}')
    if isinstance(details, list):
        for d in details: print(f'       - {d}')
    else: print(f'       {details}')
    if elapsed: print(f'       Time: {elapsed:.1f}s')

print(DIVIDER)
print('ORUNEX V51.0 - AUTONOMY INTEGRATION TEST SUITE')
print(DIVIDER)

# T1 Intent Router
print('\n[T1] Deterministic Intent Router...')
t0 = time.time()
try:
    from agents.cerebro import local_intent_scan
    cases = [
        ('haz una presentacion sobre la economia global', 'MAKE_DOC: ppt'),
        ('crea un excel con presupuesto anual para departamentos', 'MAKE_DOC: excel'),
        ('hazme un pdf sobre inteligencia artificial cuantica', 'MAKE_DOC: pdf'),
        ('necesito un calendario de agosto 2026 con tareas diarias', 'MAKE_DOC: excel'),
        ('reproduce Bad Bunny en youtube', 'YOUTUBE'),
        ('busca silenciosamente los precios del bitcoin hoy', 'HEADLESS_SEARCH'),
        ('crea una landing page para empresa de tecnologia', 'MAKE_DOC: landing'),
        ('hazme un documento word sobre marketing digital', 'MAKE_DOC: word'),
    ]
    passed, failed = [], []
    for prompt, expected in cases:
        result = local_intent_scan(prompt) or ''
        ok = expected.lower() in result.lower()
        if ok: passed.append('OK: ' + prompt[:45])
        else: failed.append('MISS: expected ' + expected + ' got: ' + result[:60])
    score, total = len(passed), len(cases)
    status = 'PASS' if score == total else ('WARN' if score >= total*0.7 else 'FAIL')
    record('T1_IntentRouter', status, ['Score: ' + str(score) + '/' + str(total)] + failed[:3], time.time()-t0, fixes=failed if failed else None)
except Exception as e:
    record('T1_IntentRouter', 'FAIL', traceback.format_exc()[:300])

# T2 LLM Tool Calling
print('\n[T2] GGUF LLM Tool-Calling...')
t0 = time.time()
try:
    from agents.cerebro import run as cerebro_run
    result = cerebro_run('Investiga silenciosamente IA 2025 y crea un PDF ejecutivo', 'TestUser', agent_mode='os')
    elapsed = time.time()-t0
    has_tag = bool(re.search(r'\[[A-Z_]+:', result or ''))
    has_good = 'MAKE_DOC: pdf' in (result or '') or 'HEADLESS_SEARCH' in (result or '')
    q = 'good' if has_good else ('partial' if has_tag else 'none')
    status = 'PASS' if has_good else ('WARN' if has_tag else 'FAIL')
    record('T2_LLM_ToolCalling', status, ['Tag quality: ' + q, 'Preview: ' + (result or '')[:100]], elapsed, fixes=None if has_good else ['Model not emitting correct compound tags'])
except Exception as e:
    record('T2_LLM_ToolCalling', 'FAIL', traceback.format_exc()[:300])

# T3 Synapse Loop
print('\n[T3] PROJECT_PLAN Multi-Step Execution...')
t0 = time.time()
try:
    from _orunex_libs import project_manager
    project_manager.ACTIVE_PROJECT = None
    steps_raw = [
        {'title': 'Busqueda Web', 'desc': '[HEADLESS_SEARCH: energia renovable 2025]'},
        {'title': 'PDF Ejecutivo', 'desc': '[MAKE_DOC: pdf | tendencias energia renovable 2025]'},
        {'title': 'Excel de Datos', 'desc': '[MAKE_DOC: excel | estadisticas energia solar 2025]'}
    ]
    project_manager.start_project('Paquete Energia Renovable', steps_raw)
    s1 = project_manager.get_current_step()
    assert s1 and s1.title == 'Busqueda Web', 'S1 mismatch'
    project_manager.mark_step_success('[HEADLESS_SEARCH done] Resultados sobre energia solar.')
    s2 = project_manager.get_current_step()
    assert s2 and s2.title == 'PDF Ejecutivo', 'S2 mismatch'
    project_manager.mark_step_success('[MAKE_DOC: pdf done] C:\\Users\\artur\\orunex_outputs\\test.pdf')
    s3 = project_manager.get_current_step()
    assert s3 and s3.title == 'Excel de Datos', 'S3 mismatch'
    project_manager.mark_step_success('[MAKE_DOC: excel done] C:\\Users\\artur\\orunex_outputs\\test.xlsx')
    final = project_manager.ACTIVE_PROJECT.get_status()
    ctx = project_manager.get_full_context()
    n_tracked = len(project_manager.ACTIVE_PROJECT.created_paths)
    record('T3_Synapse_Loop', 'PASS' if final == 'COMPLETED' else 'FAIL',
        ['Status: ' + final, 'Steps: ' + str(project_manager.ACTIVE_PROJECT.current_idx) + '/3',
         'Path memory: ' + str(n_tracked) + ' files', 'Context OK: ' + str('Busqueda' in ctx)],
        time.time()-t0)
    project_manager.ACTIVE_PROJECT = None
except Exception as e:
    record('T3_Synapse_Loop', 'FAIL', traceback.format_exc()[:400])
    try: project_manager.ACTIVE_PROJECT = None
    except: pass

# T4 Anti-Lazy Guard
print('\n[T4] Anti-Lazy Guard...')
t0 = time.time()
try:
    from _orunex_libs import project_manager
    project_manager.ACTIVE_PROJECT = None
    project_manager.start_project('Test Anti-Lazy', [{'title': 'Paso 1', 'desc': 'crear archivo'}])
    passive = 'Claro, puedo ayudarte. Primero elige el nombre del archivo.'
    project_manager.mark_step_success(passive)
    caught = project_manager.ACTIVE_PROJECT.steps[0].status == 'FAILED'
    project_manager.ACTIVE_PROJECT.steps[0].status = 'PENDING'
    project_manager.ACTIVE_PROJECT.current_idx = 0
    project_manager.mark_step_success('[CMD: mkdir test_dir] Directorio creado.')
    accepted = project_manager.ACTIVE_PROJECT.steps[0].status == 'SUCCESS'
    status = 'PASS' if (caught and accepted) else 'FAIL'
    record('T4_AntiLazyGuard', status, ['Passive rejected: ' + str(caught), 'Active accepted: ' + str(accepted)], time.time()-t0, fixes=None if caught else ['Anti-lazy logic not catching passive responses'])
    project_manager.ACTIVE_PROJECT = None
except Exception as e:
    record('T4_AntiLazyGuard', 'FAIL', traceback.format_exc()[:300])
    try: project_manager.ACTIVE_PROJECT = None
    except: pass

# T5 Path Memory
print('\n[T5] Path Memory and Cross-Step Context...')
t0 = time.time()
try:
    from _orunex_libs import project_manager
    project_manager.ACTIVE_PROJECT = None
    project_manager.start_project('Path Memory Test', [
        {'title': 'Create File', 'desc': 'create test'},
        {'title': 'Use File', 'desc': 'use it'}
    ])
    project_manager.mark_step_success('[CMD: done] Archivo listo en C:\\Users\\artur\\Documents\\informe_test.pdf')
    tracked = 'informe_test.pdf' in project_manager.ACTIVE_PROJECT.created_paths
    ctx = project_manager.get_full_context()
    in_ctx = 'Archivo listo' in ctx
    status = 'PASS' if (tracked and in_ctx) else ('WARN' if tracked else 'FAIL')
    record('T5_PathMemory', status, ['Path tracked: ' + str(tracked), 'In context: ' + str(in_ctx)], time.time()-t0)
    project_manager.ACTIVE_PROJECT = None
except Exception as e:
    record('T5_PathMemory', 'FAIL', traceback.format_exc()[:300])
    try: project_manager.ACTIVE_PROJECT = None
    except: pass

# T6 Search + File Chain
print('\n[T6] Headless Search + File Creation Chain...')
t0 = time.time()
try:
    from _orunex_libs.os_executor import intercept_and_execute
    sr = intercept_and_execute('[HEADLESS_SEARCH: blockchain latinoamerica 2025]')
    search_ok = len(sr or '') > 100
    fr = intercept_and_execute('[FILE: orunex_autonomy_test.py]\nimport datetime\nprint(str(datetime.datetime.now()))\n[/FILE]')
    file_path = os.path.join(OUT_DIR, 'orunex_autonomy_test.py')
    file_ok = os.path.exists(file_path)
    status = 'PASS' if (search_ok and file_ok) else ('WARN' if file_ok else 'FAIL')
    record('T6_Search_File_Chain', status, ['Search chars: ' + str(len(sr or '')), 'File created: ' + str(file_ok)], time.time()-t0, fixes=None if search_ok else ['Search returned too little data'])
except Exception as e:
    record('T6_Search_File_Chain', 'FAIL', traceback.format_exc()[:300])

# T7 Multi-Doc
print('\n[T7] Complex Multi-Doc Task...')
t0 = time.time()
try:
    from _orunex_libs.doc_factory import generate_pdf, generate_word
    from _orunex_libs.excel_engine import generate_excel
    topic = 'mercado criptomonedas latinoamerica 2025'
    pdf_p  = generate_pdf('Analisis ' + topic, OUT_DIR)
    word_p = generate_word('Informe ' + topic, OUT_DIR)
    xls_p  = generate_excel('Datos ' + topic, OUT_DIR)
    ok_pdf  = bool(pdf_p  and os.path.exists(pdf_p))
    ok_word = bool(word_p and os.path.exists(word_p))
    ok_xls  = bool(xls_p  and os.path.exists(xls_p))
    status = 'PASS' if all([ok_pdf, ok_word, ok_xls]) else ('WARN' if any([ok_pdf, ok_word, ok_xls]) else 'FAIL')
    record('T7_MultiDoc', status, ['PDF: ' + str(ok_pdf), 'Word: ' + str(ok_word), 'Excel: ' + str(ok_xls)], time.time()-t0)
except Exception as e:
    record('T7_MultiDoc', 'FAIL', traceback.format_exc()[:400])

# T8 scrub_output
print('\n[T8] scrub_output Signal Quality...')
t0 = time.time()
try:
    from agents.cerebro import scrub_output
    vectors = [
        ('[MAKE_DOC: pdf | analisis de mercado]', 'MAKE_DOC: pdf', 'Valid tag'),
        ('<think>analizando</think>\n[HEADLESS_SEARCH: bitcoin]', 'HEADLESS_SEARCH', 'Think-tag strip'),
        ('Okay. [FILE: test.py]\ncode\n[/FILE]', 'FILE: test.py', 'Preamble removal'),
        ('[CMD: python script.py]', 'CMD: python', 'CMD passthrough'),
        ('Lo siento, no tengo acceso a internet.', 'Comando no autorizado', 'Excuse replace'),
    ]
    passed_s, failed_s = [], []
    for raw, expected, desc in vectors:
        result = scrub_output(raw)
        ok = expected.lower() in (result or '').lower()
        if ok: passed_s.append('OK: ' + desc)
        else: failed_s.append('MISS [' + desc + ']: got ' + (result or '')[:80])
    score, total = len(passed_s), len(vectors)
    status = 'PASS' if score == total else ('WARN' if score >= total*0.7 else 'FAIL')
    record('T8_ScrubOutput', status, ['Score: ' + str(score) + '/' + str(total)] + failed_s, time.time()-t0, fixes=failed_s if failed_s else None)
except Exception as e:
    record('T8_ScrubOutput', 'FAIL', traceback.format_exc()[:300])

# T9 E2E PPT
print('\n[T9] Full E2E Pipeline (cerebro -> executor -> PPT)...')
t0 = time.time()
try:
    from agents.cerebro import run as cerebro_run
    from _orunex_libs.os_executor import intercept_and_execute
    tag = cerebro_run('haz una presentacion sobre blockchain y criptomonedas 2025', 'TestUser', agent_mode='os')
    tag_ok = 'MAKE_DOC: ppt' in (tag or '')
    file_created = False
    if tag_ok:
        result = intercept_and_execute(tag)
        ppt_files = [f for f in os.listdir(OUT_DIR) if f.endswith('.pptx')]
        file_created = len(ppt_files) > 0
    status = 'PASS' if (tag_ok and file_created) else ('WARN' if tag_ok else 'FAIL')
    record('T9_E2E_PPT', status, ['Routing: ' + ('OK' if tag_ok else 'FAIL') + ' -> ' + (tag or '')[:70], 'File created: ' + str(file_created)], time.time()-t0, fixes=None if (tag_ok and file_created) else ['PPT routing or generation issue'])
except Exception as e:
    record('T9_E2E_PPT', 'FAIL', traceback.format_exc()[:400])

# Summary
print('\n' + DIVIDER)
print('FINAL AUTONOMY REPORT:')
pass_c = sum(1 for t in REPORT['tests'] if t['status']=='PASS')
warn_c = sum(1 for t in REPORT['tests'] if t['status']=='WARN')
fail_c = sum(1 for t in REPORT['tests'] if t['status']=='FAIL')
total_t = len(REPORT['tests'])
for t in REPORT['tests']:
    icon = '[PASS]' if t['status']=='PASS' else '[WARN]' if t['status']=='WARN' else '[FAIL]'
    s = icon + ' ' + t['name']
    if 'elapsed_s' in t: s += ' (' + str(t['elapsed_s']) + 's)'
    print('  ' + s)
    if t.get('improvement_needed'):
        for fix in t['improvement_needed'][:2]: print('         -> ' + fix)
print('\n  PASS:' + str(pass_c) + '  WARN:' + str(warn_c) + '  FAIL:' + str(fail_c) + '  /' + str(total_t))
REPORT['summary'] = {'pass': pass_c, 'warn': warn_c, 'fail': fail_c, 'total': total_t}
rpath = os.path.join(OUT_DIR, 'autonomy_report_v51.json')
with open(rpath, 'w', encoding='utf-8') as ff: json.dump(REPORT, ff, indent=2, ensure_ascii=False)
print('  Report -> ' + rpath)
print(DIVIDER)
import sys; sys.exit(0 if fail_c == 0 else 1)
