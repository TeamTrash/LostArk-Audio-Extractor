# Ejecutable Windows 1.4.0

Abrir LoaAudioExtractor-1.4.0.exe con doble clic. No requiere Python instalado.
Un solo archivo contiene Python/Tk, herramientas/DLL, licencias y el catalogo
local ampliado con asociaciones verificadas. Se descomprime temporalmente al iniciarse, por lo
que el primer arranque puede tardar unos segundos. No requiere administrador.

Elegir origen y destino, buscar archivos y pulsar Extraer seleccion.
Se convierten todos los medios compatibles; las coincidencias del diccionario
reciben nombres descriptivos. Los demas conservan sin_evento + idioma + ID.

Colocar el EXE en una carpeta escribible por el usuario. Guarda config.local.json
junto al ejecutable para herramientas/CSV personalizados, nunca origen/destino.
Las herramientas integradas se usan automaticamente; no seleccionar una carpeta
temporal _MEI como ruta personalizada. No necesita tools/ externo para funcionar.

Uso local: sigue pendiente la revision de redistribucion de LAUTool y otras
dependencias. Las licencias MIT del codigo no relicencian las herramientas ni
los nombres del juego. Ver LOCAL_USE_ONLY.md y THIRD_PARTY_NOTICES.md.
El ejecutable no esta firmado digitalmente. No se ha probado en todas las
versiones de Windows ni en un equipo limpio independiente.

## Compilacion

Usar Windows x64, Python 3.12 con Tcl/Tk y un entorno aislado:

```text
python -m pip install pyinstaller==6.22.3
python build_windows.py --output ../releases/1.4.0/windows
```

No sobrescribe los ZIP de codigo existentes. PyInstaller recoge Python/Tk;
build_windows.py incluye solo recursos permitidos, sin configuracion personal,
audios, paquetes PCK/WEM, ni muestras. Genera MANIFEST.json y SHA256SUMS.txt.

Diagnostico opcional del runtime empaquetado:

```text
LoaAudioExtractor-1.4.0.exe --self-test REPORTE.json
```

Comprueba interfaz, herramientas y catalogo, y termina. Para probar conversion,
agregar --sample ARCHIVO.pck --output DESTINO (se puede repetir --sample).
No hace busquedas automaticas en instalaciones del juego.

Referencias de compilacion:
- https://pyinstaller.org/en/stable/runtime-information.html
- https://pyinstaller.org/en/stable/usage.html


