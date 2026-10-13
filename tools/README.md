# Herramientas locales de la aplicacion

Estructura detectada automaticamente:

- LAUTool_0.3/LAUTool_steam.exe
- quickbms/bin/quickbms.exe (documentacion disponible junto al ejecutable)
- quickbms/wwise_pck_extractor.bms
- vgmstream/bin/vgmstream-cli.exe (con todas sus DLL, COPYING y documentacion)
- ffmpeg/ffmpeg.exe y ffmpeg/LICENSE.txt (para MP3; libmp3lame)

La distribucion publica *-source.zip contiene solo este README, no los ejecutables ni el script.
El paquete *-local-tools.zip incluye las herramientas y DLL enumeradas arriba.
Es para uso local; consultar ../LOCAL_USE_ONLY.md antes de compartir paquetes.
Obtener las dependencias por separado y conservar sus propias licencias.
En el entorno de desarrollo pueden existir copias locales verificadas por SHA256.
No se necesita LAUTool_ru o wwiser para el flujo PCK/WEM -> WAV/MP3.
FFmpeg es opcional para WAV y necesario para MP3 o WAV + MP3.
Conservar todas las DLL. Python/Tkinter sigue siendo externo a esta carpeta.
No publicar la carpeta local completa. Ver ../THIRD_PARTY_NOTICES.md y usar
../build_release.py --source-only para generar el paquete publico sin binarios.
