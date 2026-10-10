# Paquete local con herramientas

El archivo *-local-tools.zip contiene la aplicacion junto con las herramientas
instaladas por el usuario: LAUTool Steam, QuickBMS, script PCK y vgmstream/DLLs.
Mantener toda la carpeta tools junto al programa. Python/Tkinter sigue siendo
un requisito externo; no es un EXE autonomo ni incluye el runtime de Python.

Este paquete es para uso local. No esta aprobado para redistribucion publica:
no se ha confirmado la licencia de redistribucion de LAUTool ni auditado todas
las dependencias binarias. El MIT del programa NO se aplica a estas herramientas.
Se conservan los avisos/documentacion disponibles y los hashes de cada archivo.

Para publicar codigo abierto utilizar *-source.zip, que no contiene binarios
externos ni el script PCK. Ver THIRD_PARTY_NOTICES.md para procedencia y limites.
El paquete local incluye data/event_names.local.json: asociaciones de nombres
extraidas del catalogo local, sin audio ni rutas personales. Es un catalogo
parcial de musica/siderales, no un diccionario completo del juego. Mantener data/
junto a tools/. Estos datos no se incluyen ni quedan relicenciados en source.zip.
Ningun paquete incluye configuraciones/rutas personales.
