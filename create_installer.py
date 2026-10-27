import os
import shutil
import zipfile
import tempfile
import sys

def create_installer():
    # Carpeta temporal
    with tempfile.TemporaryDirectory() as tmpdir:
        # Copiar todos los archivos de dist/
        dist_src = "dist"
        pkg_dir = os.path.join(tmpdir, "package")
        shutil.copytree(dist_src, pkg_dir)

        # Añadir post_install.bat
        shutil.copy("installer/post_install.bat", pkg_dir)

        # Crear ZIP
        zip_path = os.path.join(tmpdir, "orunex_package.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(pkg_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    arc_path = os.path.relpath(full_path, pkg_dir)
                    zf.write(full_path, arc_path)

        # Leer el ZIP como binario
        with open(zip_path, "rb") as f:
            zip_data = f.read()

        # Script de extracción
        extractor = f'''
import os
import sys
import zipfile
import tempfile

def main():
    exe_path = sys.executable if getattr(sys, 'frozen', False) else __file__
    with tempfile.TemporaryDirectory() as tmp:
        zip_path = os.path.join(tmp, "data.zip")
        with open(exe_path, "rb") as f:
            content = f.read()
            start = content.find(b"PK\\x03\\x04")
            if start == -1:
                print("Error: No se encontró el paquete.")
                return
            with open(zip_path, "wb") as zf:
                zf.write(content[start:])
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(".")
        os.system("post_install.bat")

if __name__ == "__main__":
    main()
'''

        # Guardar el instalador final
        installer_path = "Orunex_Installer.exe"
        with open(installer_path, "wb") as f:
            # Escribir el extractor de Python empaquetado
            import subprocess
            extractor_py = os.path.join(tmpdir, "extractor.py")
            with open(extractor_py, "w") as ef:
                ef.write(extractor)
            
            # Compilar extractor con PyInstaller
            subprocess.run([
                sys.executable, "-m", "PyInstaller",
                "--onefile",
                "--noconsole",
                "--name", "Orunex_Installer_TEMP",
                extractor_py
            ], cwd=tmpdir, capture_output=True)

            # Leer el ejecutable generado
            temp_exe = os.path.join(tmpdir, "dist", "Orunex_Installer_TEMP.exe")
            with open(temp_exe, "rb") as ef:
                exe_data = ef.read()
            
            f.write(exe_data)
            f.write(zip_data)

        print(f"[EXITO] Instalador creado: {os.path.abspath(installer_path)}")

if __name__ == "__main__":
    create_installer()