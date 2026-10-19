# Build del lanzador (Karmed Export)

Genera un ejecutable único. **No requiere Python en la máquina destino.**
PyInstaller compila para el sistema donde se ejecuta, así que el `.exe` de
Windows se construye en Windows y el de macOS en una Mac.

## Requisitos (una vez, en la máquina de build)

- [uv](https://docs.astral.sh/uv/) instalado.
- Clonar/copiar este repo y dentro correr `uv sync` (instala PyInstaller y deps).

## Icono

El `.spec` ya usa el icono según el SO: `assets/icon.icns` (macOS) y
`assets/icon.ico` (Windows). Para regenerarlos desde el arte base:

```bash
uv run python assets/make_icon.py        # icon.png
# luego icon.ico (Pillow) e icon.icns (iconutil) — ver assets/
```

## macOS

```bash
uv run pyinstaller KarmedExport.spec --noconfirm
```

El binario queda en `dist/KarmedExport`.

> En Windows el `.exe` muestra el icono directo. En macOS, un binario *onefile*
> de consola puede mostrarse con icono genérico en Finder (el icono igual queda
> embebido); el funcionamiento no cambia.

> Primer arranque: macOS (Gatekeeper) escanea el binario y puede tardar ~10 s.
> Si aparece "no se puede abrir porque es de un desarrollador no identificado",
> clic derecho → Abrir, o `xattr -dr com.apple.quarantine dist/KarmedExport`.

## Windows

En una PC Windows, con uv instalado:

```powershell
uv sync
uv run pyinstaller KarmedExport.spec --noconfirm
```

El binario queda en `dist\KarmedExport.exe`.

## Compilar en la nube (GitHub Actions) — sin PC Windows

El repo trae `.github/workflows/build.yml`, que compila **Windows y macOS** en
los runners de GitHub. Dos formas de dispararlo:

- **A mano:** pestaña **Actions** → *Build launchers* → **Run workflow**.
- **Con un tag de versión:** `git tag v1.0.0 && git push --tags` → además de
  compilar, adjunta los ejecutables a un **Release**.

Los binarios quedan como **artifacts** descargables al final de cada corrida
(`KarmedExport-windows` y `KarmedExport-macos`).

## Cómo lo usa el usuario final

1. Copia el ejecutable a una carpeta propia (ej. `Karmed`).
2. Doble clic → se abre una ventana y el navegador en `http://127.0.0.1:8771`.
3. En **Configuración** pone usuario, contraseña (y sucursal si el login la pide)
   y pulsa **Guardar**. Esto crea un `.env` **junto al ejecutable**.
4. **Cargar pacientes** → busca → **Exportar a Excel**.

Archivos que el ejecutable crea en su misma carpeta:

- `.env` — credenciales (NO compartir).
- `data/patients.json` — cache del listado para reabrir sin re-descargar.
- `exports/` — los `.xlsx` generados.

Para detener: cerrar la ventana de consola. El puerto se libera solo.

## Puerto

- Usa el **8771** por defecto (poco común, para no chocar con otras apps).
- Si está ocupado, **busca el siguiente libre** (8772, 8773…) y abre el navegador
  en el que haya tomado. Nunca falla por "puerto en uso".
- Se puede forzar con la variable `KARMED_PORT` en el `.env` (ej. `KARMED_PORT=9000`).

## Instancia única

Si el usuario hace **doble clic de nuevo** estando ya abierto, la segunda copia
**no levanta otro servidor**: detecta la que ya corre (vía `/api/health`), abre
el navegador en esa y se cierra sola. Así nunca hay dos servers ni pestañas
duplicadas. Si otra app ajena ocupa el 8771, recién ahí usa el siguiente libre.
