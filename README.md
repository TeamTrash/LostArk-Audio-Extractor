# Lost Ark Audio Extractor

Codigo abierto bajo licencia MIT.
Proyecto independiente, sin afiliacion oficial con el juego. La licencia del
codigo no otorga derechos sobre contenidos del juego ni herramientas externas.

## Paquete publico

Aplicacion local para Windows. Python 3.10 o posterior con Tcl/Tk (tkinter).
No requiere pip, cuenta, servidor ni conexion a Internet para extraer.
Primera version: PCK/WEM -> WAV. No modifica archivos del juego.

## Inicio

1. Instalar Python para Windows con Tcl/Tk y el lanzador `py`.
2. Abrir Iniciar.cmd, o ejecutar `python app.py`.
3. Las herramientas de tools/ se detectan automaticamente. Revisarlas en
   Herramientas y nombres; se pueden elegir otras versiones manualmente.
4. Elegir WwiseAudioPackage (o una carpeta de muestras) y un destino separado.
5. Buscar archivos, filtrar, seleccionar y pulsar Extraer seleccion a WAV.


Usar primero un WEM o PCK pequeno. WAV puede ocupar mucho mas que el origen.
La comprobacion de espacio inicial es aproximada, no garantiza espacio para
todo el lote. Los medios intermedios usan espacio temporal y se eliminan al acabar.

## Dependencias externas
 
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
Si el nombre no es compatible se conserva.
 

Extrae WEM de PCK y convierte WEM sueltos. Los BNK intermedios se eliminan;
esta version no renderiza eventos Wwise ni extrae automaticamente todos los medios embebidos
en BNK. Las composiciones, voces y bancos interdependientes pueden requerir wwiser
y el flujo avanzado de investigacion. No incluye MP3 ni funciones de modificacion.

los datos del juego usados en esas comprobaciones no se distribuyen.
