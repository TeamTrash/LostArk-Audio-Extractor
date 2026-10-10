# Lost Ark Audio Extractor 1.3.2

Codigo abierto bajo licencia MIT. Ver LICENSE y THIRD_PARTY_NOTICES.md.
Proyecto independiente, sin afiliacion oficial con el juego. La licencia del
codigo no otorga derechos sobre contenidos del juego ni herramientas externas.

## Paquete publico

LoaAudioExtractor-1.3.2-source.zip contiene codigo, pruebas, lanzador e instrucciones.
No es un EXE autonomo: requiere Python y las herramientas externas configuradas
por cada usuario. No incluye audios, datos del juego, rutas personales ni binarios
de terceros. Ver DEPENDENCIES.json, CHANGELOG.md y RELEASE.md.

LoaAudioExtractor-1.3.2-local-tools.zip incluye ademas la carpeta tools con las
herramientas y DLL instaladas. Es para uso local, no un paquete autorizado para
redistribuir herramientas de terceros. Ver LOCAL_USE_ONLY.md. Requiere Python.

Aplicacion local para Windows. Python 3.10 o posterior con Tcl/Tk (tkinter).
No requiere pip, cuenta, servidor ni conexion a Internet para extraer.
Primera version: PCK/WEM -> WAV. No modifica archivos del juego.

En el entorno de desarrollo puede existir un lanzador personal; no se incluye
en la distribucion publica.

## Inicio

1. Instalar Python para Windows con Tcl/Tk y el lanzador `py`.
2. Abrir Iniciar.cmd, o ejecutar `python app.py`.
3. Las herramientas de tools/ se detectan automaticamente. Revisarlas en
   Herramientas y nombres; se pueden elegir otras versiones manualmente.
4. Elegir WwiseAudioPackage (o una carpeta de muestras) y un destino separado.
5. Buscar archivos, filtrar, seleccionar y pulsar Extraer seleccion a WAV.

Las cabeceras Nombre desofuscado, Carpeta / archivo original y KB alternan orden ascendente
y descendente al pulsarlas. La flecha indica el orden activo. KB usa bytes reales,
no el texto redondeado; los tamanos desconocidos quedan al final. El orden se
mantiene al filtrar y no cambia que archivos estan seleccionados al pulsar la cabecera.
Cada tamano se muestra con dos decimales y sufijo KB (1 KB = 1000 bytes).

Usar primero un WEM o PCK pequeno. WAV puede ocupar mucho mas que el origen.
La comprobacion de espacio inicial es aproximada, no garantiza espacio para
todo el lote. Los medios intermedios usan espacio temporal y se eliminan al acabar.

## Dependencias externas

La carpeta local apps/LoaAudioExtractor/tools contiene copias de las herramientas
ya instaladas, incluidas las DLL de vgmstream y documentacion disponible.
Se detectan desde la carpeta de la app, sin depender de tools/audio_converters.
Las rutas internas se guardan relativas; las configuraciones antiguas se migran
al cargar conservando otras rutas personalizadas validas de herramientas.
Python sigue siendo un requisito externo. El ZIP publico *-source.zip solo contiene
codigo/documentacion/pruebas. Para publicar, usar el ZIP generado con build_release.py,
no una copia de toda la carpeta local. Los usuarios colocan sus herramientas en
tools/ conservando subcarpetas, DLL y avisos propios de cada distribucion.

- LAUTool Steam 0.3: version proporcionada por el usuario; copia local en tools/LAUTool_0.3.
- QuickBMS: https://aluigi.altervista.org/quickbms.htm
- Script PCK: https://github.com/bnnm/wwiser-utils/blob/master/scripts/wwise_pck_extractor.bms
- vgmstream: https://github.com/vgmstream/vgmstream-releases/releases
  Conservar todas sus DLL junto al ejecutable, no solo el EXE.

No se descargan dependencias automaticamente ni se buscan claves. Comprobar las
licencias de cada herramienta antes de redistribuirla; esta carpeta no concede
derechos sobre herramientas o archivos del juego. No se garantiza compatibilidad
con todos los clientes o actualizaciones de Lost Ark.

## Nombres y limites

Los nombres PCK/WEM compatibles se desofuscan automaticamente sin CSV, usando
una adaptacion del decodificador de lostark-explorer (MIT, licencia incluida en
licenses/). La tabla mantiene la ruta/nombre original y permite buscar u ordenar
por el nombre recuperado. Se usa tambien al nombrar las salidas de extraccion.
PCK recupera nombres como SOUND_BGM_YORN; WEM recupera IDs, no titulos de canciones.
Si el nombre no es compatible se conserva sin inventar datos.

Opcional: audio_inventory.csv permite sobrescribir nombres, y CATALOGO.csv aporta
asociaciones entre medios y eventos descriptivos ya investigadas. La desofuscacion
no reconstruye eventos Wwise ni identifica semanticamente todos los sonidos.

El paquete local-tools incluye data/event_names.local.json con 5238 asociaciones
conocidas del catalogo de musica/siderales. Se carga automaticamente cuando el
campo Catalogo queda vacio. Un CSV elegido manualmente reemplaza ese catalogo.
Extraer seleccion a WAV desempaqueta y convierte TODOS los medios disponibles:
los que coinciden con el diccionario reciben su nombre descriptivo durante la
conversion; los demas conservan sin_evento + idioma + ID. No se filtran ni omiten
audios por carecer de nombre. Actualizar nombres no es necesario para nuevas extracciones.
No es un diccionario completo del juego: voces, clases y otros bancos pueden no
estar cubiertos. No se asignan eventos de otro idioma/paquete solo por coincidir el ID.
El paquete publico source no incluye estos datos del juego.

Para audios existentes de v1.1 o posterior, elegir su carpeta Destino y pulsar
Actualizar nombres del destino. No necesita origen ni reconversion; solo renombra
WAV registrados como sin_evento con coincidencia exacta de idioma, paquete e ID.
Los nombres ya asignados se conservan. Muestra cuantos quedaron sin asociacion.
Respalda manifiestos en .loa_audio/naming_backups y conserva los nombres anteriores.
No ejecutar extraccion y reparacion desde dos instancias sobre el mismo destino.
Si se interrumpe un renombrado, repetir esta accion antes de reanudar extraccion.

CLI (sin --apply solo informa):
`python repair_names.py --output DESTINO --catalog CATALOGO.csv --apply`

Extrae WEM de PCK y convierte WEM sueltos. Los BNK intermedios se eliminan;
esta version no renderiza eventos Wwise ni extrae automaticamente todos los medios embebidos
en BNK. Las composiciones, voces y bancos interdependientes pueden requerir wwiser
y el flujo avanzado de investigacion. No incluye MP3 ni funciones de modificacion.

## Salida y seguridad

Si el nombre desofuscado empieza por un numero (incluidos nombres como 7voice),
sus WAV van a la carpeta comun Audios_numericos. Los demas conservan una carpeta
con el nombre desofuscado del archivo fuente. Los WAV quedan directamente dentro:

```text
destino/
  Audios_numericos/
    sin_evento__idioma__ID.wav
  SOUND_BGM_YORN/
    nombre_evento__idioma__ID.wav
  .loa_audio/
    identificador.json
    identificador.log
```

Las carpetas de paquetes contienen solo audio, sin subcarpetas ni listas o logs.
Los WAV no llevan un hash final. Si coinciden nombre, idioma e ID entre audios
registrados, se agrega _2, _3, etc. Los archivos no registrados no se sobrescriben.
Los WAV anteriores conservan sus nombres al reanudar; Actualizar nombres es explicito.
Si no hay nombre conocido se conserva sin_evento y el ID; no se inventan titulos.
.loa_audio es una unica carpeta auxiliar para todos los paquetes: no borrarla si
se quiere conservar la reanudacion. No se promete que Windows la oculte.

Los WAV se publican tras validar el PCM. Los temporales PCK/WEM/BNK y WAV parciales
se eliminan al finalizar, fallar o cancelar. Un corte de energia puede dejar
temporales; no hay limpieza automatica de restos de otras ejecuciones.
Los WAV ya validados se conservan y reutilizan al reintentar. Si cambia el archivo
fuente, usar otro destino. No se sobrescriben archivos ajenos a los manifiestos.
Desde v1.3.2, si se borra un WAV o su carpeta pero se conserva .loa_audio,
Extraer seleccion a WAV detecta los ausentes y los regenera desde el origen.
Los WAV existentes no se reconvierten. Los nombres conocidos se conservan aun
sin catalogo disponible. No borrar .loa_audio para solucionar este caso.
Un WAV corrupto o inaccesible no se trata como borrado ni se sobrescribe.
Si hay un renombrado interrumpido, usar primero Actualizar nombres del destino.
Las extracciones v1.0/v1.1 existentes no se reorganizan ni duplican: para aplicar el
nuevo esquema a esos mismos paquetes, seleccionar un destino nuevo.

Cancelar detiene la herramienta en ejecucion. Cerrar durante trabajo pide
confirmacion y espera la cancelacion. Registros por fuente: .loa_audio/*.log.
Las rutas de herramientas y CSV opcionales se guardan en config.local.json;
no compartir ese archivo. Origen y destino solo se mantienen durante la sesion:
no se guardan y aparecen vacios al abrir, incluso con una configuracion antigua.

## Pruebas

`python -m unittest discover -s tests -v`

Pruebas de motor, configuracion, tabla, nombres y empaquetado. Ventana comprobada
a 1080x760 y 820x620. Extraccion real de un WEM (82.83 s) y un PCK Papunika (63 s),
PCM validado y SHA256 de las fuentes sin cambios. No garantiza otros bancos.
Desofuscacion contrastada con 1456 nombres del inventario local, sin diferencias.
Los datos del juego usados en esas comprobaciones no se distribuyen.
