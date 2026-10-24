# Lost Ark Audio Extractor — 1.4.7

Extrae música, voces y efectos de Lost Ark desde archivos **PCK/WEM** y los convierte a **WAV, MP3 o ambos**. Funciona localmente en Windows y no modifica los archivos originales.

## Uso rápido

1. Abre `LoaAudioExtractor-1.4.7.exe` (no requiere Python).
2. Elige la **Carpeta de audios** y un **Destino** separado.
3. Pulsa **Buscar archivos** y selecciona los que quieres extraer.
4. Elige el formato, el idioma de los nombres y, opcionalmente, **Solo nombre descriptivo**.
5. Pulsa **Extraer selección** y después **Abrir destino**.

## Funciones

| Opción | Qué hace |
| --- | --- |
| Buscar archivos / Filtro | Lista los archivos compatibles y permite buscarlos. |
| Seleccionar visibles | Selecciona todos los resultados del filtro. |
| Formato | Exporta a WAV, MP3 o WAV + MP3. |
| Idioma de los nombres | Elige títulos en español, inglés o coreano; no cambia el idioma del audio. |
| Solo nombre descriptivo | Guarda nombres como `Aldea de las Nia.wav`. Los duplicados reciben `_2`, `_3`, etc. |
| Extraer selección / Cancelar | Inicia o detiene la extracción. Al repetirla, reutiliza los resultados registrados. |
| Actualizar nombres del destino | Renombra audios registrados sin reconvertirlos; aplica el idioma y estilo elegidos. |
| Abrir destino | Abre la carpeta de resultados. |
| Herramientas y nombres | Configura y verifica herramientas; permite usar inventarios y catálogos CSV opcionales. |

## Nombres y organización

- Recupera nombres de archivos compatibles y usa un diccionario de eventos y títulos.
- Organiza la salida por nombre desofuscado y archivo original de procedencia.
- Nombre completo: `Aldea de las Nia__bgm_jukebox_m36_2d_play__SFX__755910078.wav`.
- Sin título disponible, conserva el nombre técnico; sin evento identificado, usa `sin_evento` con idioma e ID.
- **Coreano:** el selector está disponible, pero las bases incluidas aún no contienen títulos coreanos.
- Deja **Catálogo CSV** vacío para utilizar el diccionario integrado en el EXE. Conserva `.loa_audio` para reanudar y actualizar nombres.

Código bajo licencia **MIT**. Proyecto independiente, sin afiliación oficial con Lost Ark.
