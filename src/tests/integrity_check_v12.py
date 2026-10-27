import os
import sys
import importlib.util
import traceback

def audit_integrity():
    print("\n" + "="*60)
    print("      ORUNEX CODE INTEGRITY AUDIT V12.2")
    print("="*60 + "\n")

    proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    sys.path.insert(0, proj_root)

    files_found = 0
    files_valid = 0
    failures = []

    # Directories to audit
    audit_dirs = ["agents", "_orunex_libs", "widgets", "integrations", "utils"]
    
    # Mock some problematic imports if necessary (e.g. windows/gui)
    # But usually, just importing the module doesn't start the Tk loop if properly guarded.

    for d in audit_dirs:
        dir_path = os.path.join(proj_root, d)
        if not os.path.exists(dir_path): continue

        for f in os.listdir(dir_path):
            if f.endswith(".py") and f != "__init__.py":
                files_found += 1
                module_name = f"{d}.{f[:-3]}"
                
                try:
                    # Clear from sys.modules if already there to force check
                    if module_name in sys.modules:
                        del sys.modules[module_name]
                    
                    spec = importlib.util.find_spec(module_name)
                    if spec:
                        importlib.import_module(module_name)
                        print(f" [OK] {module_name}")
                        files_valid += 1
                    else:
                        print(f" [ERR] {module_name} (No se pudo encontrar el spec)")
                        failures.append(module_name)
                except Exception as e:
                    print(f" [FAIL] {module_name}")
                    failures.append(f"{module_name}: {str(e)}")
                    # Uncomment to see full trace:
                    # traceback.print_exc()

    print("\n" + "="*60)
    print(f" TOTAL COMPROBADO: {files_found}")
    print(f" ARCHIVOS VÁLIDOS: {files_valid}")
    print(f" ESTADO: {'SANO ✅' if files_found == files_valid else 'DEPURACIÓN REQUERIDA 🛠️'}")
    
    if failures:
        print("\n [!] FALLOS DETECTADOS:")
        for fail in failures:
            print(f"   - {fail}")
    print("="*60 + "\n")

if __name__ == "__main__":
    audit_integrity()
