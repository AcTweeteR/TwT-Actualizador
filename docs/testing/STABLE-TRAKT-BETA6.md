# Stable basada en Beta6

Origen: commit 45d432f239afb520b28ec360b2ba85efb7e4f385 y los ZIP Testing verificados. Las versiones Stable son Skin 1.2.39, Service 0.4.97 y XStream 1.1.2.39.

La reconstrucción de identidades se comprobó con un perfil temporal y transporte simulado. La reproducción de estados en Mac se contrastó con los almacenes locales; esta promoción no aporta una nueva validación visual ni física en Windows, Android o tvOS. No se ha validado físicamente el bloqueo Windows.

Las restauraciones de escritura siguen deshabilitadas y los avances susceptibles de duplicar script.trakt permanecen retenidos. La cola Trakt no se reinició ni se realizaron exportaciones durante la publicación.

El índice Stable anterior se conserva en manifests/archive/beta37-stable-addons.xml y todos sus paquetes históricos permanecen disponibles. Para revertir, recuperar ese índice y regenerar su MD5 desde ese archivo en un commit de reversión; verificar su SHA-256 3f0f219bad7736ada4c33386c1b7af00db2536d973b9e3d409a1f7550873c8cf antes de distribuirlo.
