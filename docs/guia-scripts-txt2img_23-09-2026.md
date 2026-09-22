# Última modificación: 2026-09-23

# Guía de los scripts de txt2img/img2img en Forge Neo

Qué hace cada acordeón del panel de scripts, cuándo conviene activarlo y con qué valores, **para esta máquina concreta y para los tres modelos que usas**. Los parámetros y los defaults que aparecen aquí están leídos del código de cada script en la imagen actual, no de la documentación upstream.

## Tu contexto (de aquí salen todas las recomendaciones)

| Dato | Valor |
|---|---|
| GPU | RTX 4060, 8.188 MiB (8 GB), compute capability **8.9** |
| Flags de arranque | `--cuda-malloc --lowvram --fp8_e4m3fn-unet --reserve-vram 2 --pin-shared-memory --mmap-torch-files` |
| Perfil `make wan` | lo anterior + `--use-ck-attention` |
| Modelos habituales | Flux.2 Klein 9B turbo, Krea 2 turbo, Wan 2.2 turbo |

Tres consecuencias de esto condicionan casi todo lo que sigue:

1. **Con `--lowvram`, el cuello de botella es el trasiego de pesos entre RAM y VRAM, no el cálculo.** Está medido en esta máquina: con Krea 2 a 8 pasos, generar a 768×768 cuesta 25,9 s y a 1280×1280 cuesta 26,3 s. Cuadruplicar los píxeles sale casi gratis porque el tiempo se lo come el offload. Por eso, cualquier script que prometa acelerar el *cálculo* de la atención te dará mucho menos de lo que anuncia a resoluciones bajas.
2. **`--cuda-malloc` bloquea dos de los presets de Torch Compile.** El script los rechaza explícitamente.
3. **Los modelos turbo van a 4–8 pasos.** Cualquier técnica que funcione saltándose pasos o reservando pasos de "calentamiento" no tiene margen donde operar.

## Resumen: qué activar y qué no

| Script | Veredicto para tu stack |
|---|---|
| Sparse Attention Integrated | Solo para **Wan 2.2** (vídeo). En imagen, únicamente a partir de 1280 px |
| img2img Hires Fix | Sí, es la forma de tener hires fix en img2img. Usa 1.5× en vez de 2× |
| Dynamic Prompts | Sí, para wildcards. Vigila el modo combinatorio |
| ReActor | Solo como pasada final y aparte. Para identidad en Krea 2, Identity Edit es mejor |
| ControlNet Integrated | Sí, tienes el ControlNet de depth de Krea 2. No aplica a Klein ni a Wan |
| MultiDiffusion Integrated | Solo para ampliar a 3–4K en img2img. No para txt2img directo |
| Never OOM Integrated | **VAE tiled: sí, déjalo puesto.** UNet: no, es redundante con `--lowvram` |
| ImageStitch Integrated | Sí, es de los más útiles: da multi-imagen en Klein y último fotograma en Wan I2V |
| Krea2 Moodboard | Sí, es tu transferencia de estilo para Krea 2 |
| Krea2 Identity Edit | Sí, es tu edición con identidad para Krea 2 |
| Spectrum Integrated | **No.** Es incompatible en la práctica con 8 pasos |
| Torch Compile Integrated | Solo para lotes largos a resolución fija, y solo con dos de los presets |

---

## Sparse Attention Integrated

Sustituye la atención densa por el kernel `sol_attn` de Comfy-Kitchen, que descarta bloques de la matriz de atención por debajo de un umbral. El ahorro crece con el cuadrado de la longitud de secuencia, así que **su utilidad depende por completo de cuántos tokens tenga tu generación**.

Tu GPU es compatible: el kernel exige sm_80 o superior y tú tienes sm_89. Pero hay más condiciones que el script comprueba en cada llamada, y si alguna falla vuelve a atención densa en silencio (salvo que actives `Verbose`): la dimensión por cabeza debe ser exactamente 128, los tensores deben ser bf16 o fp16, y solo se aplica a auto-atención, nunca a atención cruzada.

**Cuándo sí.** En Wan 2.2, siempre. Un vídeo de 81 fotogramas a 832×480 ronda los 32.000 tokens, y ahí la atención sí es el coste dominante. En imagen, el número de tokens es aproximadamente `(ancho/16) × (alto/16)`:

| Resolución | Tokens aprox. |
|---|---|
| 768×768 | 2.304 |
| 1024×1024 | 4.096 |
| 1280×1280 | 6.400 |
| 1536×1536 | 9.216 |

Compara eso con el default de **Tokens Threshold, que es 4096**: a 768 px el script no se activa nunca, y a 1024 px está justo en la frontera. Es decir, con la configuración de fábrica no notarás absolutamente nada hasta pasar de 1024 px, y no es un fallo, es que está diseñado para no malgastar esfuerzo donde no rinde.

**Cuándo no.** En imagen por debajo de 1280 px no merece la pena. Y ojo con una interacción que no es evidente: este script instala un `optimized_attention_override`, es decir, **reemplaza** el backend de atención activo. Si arrancas con `make wan` (que activa la atención INT8 de Comfy-Kitchen), Sparse Attention pasa por encima de ella. No se suman; compiten. Prueba las dos por separado antes de decidir.

**Valores.** Deja `Tau` en 1.25 y súbelo solo si necesitas más velocidad a cambio de calidad; por encima de 2.0 empiezan a aparecer artefactos en texturas finas. El `Timestep Range` de fábrica, 0.15–0.85, mantiene densos el primer y el último tramo del muestreo, que es donde se decide composición y detalle final. **Con turbo esto importa más de lo normal**, porque con 8 pasos cada paso pesa un octavo del resultado: si ves que la composición se desordena, estrecha a 0.20–0.80 antes de tocar `Tau`. `Extra Tokens` a 0 y `Dense Blocks` vacío están bien para empezar; si un modelo concreto te da artefactos, `Dense Blocks` con `0, 1` deja densos los primeros bloques, que son los más sensibles. Activa `Verbose` la primera vez para confirmar en el log que de verdad está entrando en modo disperso.

## img2img Hires Fix

La pestaña img2img no tiene hires fix nativo; esta extensión lo añade. Hace una segunda pasada ampliando la imagen con un upscaler y volviendo a muestrear encima.

**Cuándo sí.** Cuando quieras rematar detalle sobre una imagen que ya te gusta. Es el patrón correcto en tu máquina: una primera pasada a resolución cómoda y una segunda para subir, en vez de intentar generar de una vez a 2K.

**Cuándo no.** Si vas a cambiar mucho la imagen, ajusta el prompt y regenera; no uses el hires fix como excusa.

**Valores.** Los defaults son upscaler `R-ESRGAN 4x+`, `Upscale by` 2.0 y `Denoising strength` 0.33. Baja el factor a **1.5**: con 8 GB y `--lowvram`, un 2× desde 1024 px te lleva a 2048 px y el decodificado del VAE es donde suelen aparecer los cuelgues (para eso está el VAE tiled de Never OOM, más abajo). El denoise 0.33 es un buen punto de partida; por debajo de 0.25 apenas añade detalle y por encima de 0.45 empieza a inventarse cosas y a duplicar rasgos.

Dos campos tienen un comportamiento que conviene conocer: `Hires steps` y `CFG Scale` **valen 0 por defecto, y ese 0 significa "hereda lo de la primera pasada"**. Con modelos turbo eso es justo lo que quieres, porque heredas el CFG 1. No pongas CFG a mano aquí salvo que sepas que tu checkpoint lo admite; ponerle 7 a un turbo te quemará la imagen.

## Dynamic Prompts

Plantillas de prompt: alternativas entre llaves (`{rojo|verde|azul}`), wildcards de fichero (`__film/styles/film-stocks__`) y generación combinatoria.

**Cuándo sí.** Para explorar variantes y para los wildcards del pack de Krea 2 que ya tienes instalado. Es gratis en tiempo de cómputo, solo reescribe texto.

**Cuándo no.** Con cuidado con **Combinatorial generation**: no elige al azar, genera *todas* las combinaciones. Ya te pasó, con el aviso de "Prompt matrix will create 81 images". Para uso normal deja el modo aleatorio y controla la cantidad con el batch.

**Valores.** Deja `Fixed seed` desactivado (con semilla fija y prompts variables pierdes la comparación limpia). Si quieres comparar wildcards de forma rigurosa, al contrario: fija la semilla y usa el modo combinatorio con un batch pequeño, para que la única variable sea el texto. Ten en cuenta que **Magic Prompt no está disponible** en esta imagen: se instaló `dynamicprompts` sin los extras a propósito, porque arrastraban `transformers[torch]` y habrían pisado la versión de torch de la imagen.

## ReActor

Intercambio de caras por post-proceso. Detecta la cara en la imagen generada y le pega la de tu imagen fuente con el modelo `inswapper`, opcionalmente pasando un restaurador facial por encima. No toca el sampler ni el modelo de difusión: actúa sobre el resultado ya terminado.

**Cuándo sí.** Cuando necesites la misma cara en imágenes generadas con modelos que no tienen mecanismo propio de identidad. Funciona con cualquier checkpoint precisamente porque es ajeno al modelo.

**Cuándo no.** **Para Krea 2, Identity Edit es claramente mejor** y es la diferencia entre dos enfoques: Identity Edit mete la referencia en el condicionamiento, así que el modelo genera desde el principio a esa persona con su iluminación y su postura coherentes; ReActor pega una cara al final, y se nota en los bordes y cuando la pose o la luz no encajan. Usa ReActor como red de seguridad o para retocar una imagen ya buena, no como tu método principal de identidad en Krea 2.

**Valores.** Con `Restore Face` usa CodeFormer con visibilidad 1.0 y peso alrededor de 0.5; en CodeFormer, pesos bajos favorecen la calidad y altos la fidelidad al píxel original, y 0.5 es el compromiso habitual. Activa `Face Mask Correction` si ves costuras rectangulares alrededor de la cara. En tu máquina, ten presente que ReActor carga sus propios modelos ONNX en la GPU: con 8 GB ya justos, lo más limpio es aplicarlo en una pasada aparte sobre imágenes ya generadas en vez de dejarlo activo durante lotes largos.

## ControlNet Integrated

Condiciona la generación con una guía estructural (profundidad, bordes, pose...). Requiere un modelo ControlNet **entrenado para tu checkpoint concreto**, y eso es lo que decide si te sirve o no.

**Cuándo sí.** Tienes `krea2DepthControlnet_v10.safetensors` en `Models/ControlNet`, así que puedes controlar la profundidad con Krea 2. Es la vía para reproducir una composición o una perspectiva concreta.

**Cuándo no.** No hay nada que puedas usar con Klein 9B ni con Wan 2.2 por esta vía: son arquitecturas distintas y el ControlNet de Krea 2 no vale para ellas. El control de movimiento en Wan va por otros mecanismos, no por este acordeón. Y con un único modelo de depth disponible, no cuentes con canny, pose ni tile para Krea 2.

**Valores.** Para el ControlNet de depth, empieza con `Control Weight` 0.6–0.8; a 1.0 la guía suele imponerse tanto que el prompt pierde influencia sobre la composición. Deja `Starting Control Step` en 0 y baja `Ending Control Step` a 0.7–0.8 para que los últimos pasos queden libres y el modelo remate el detalle sin la guía encima. Con turbo a 8 pasos, esos porcentajes se traducen en muy pocos pasos, así que los cambios se notan a saltos: no esperes un ajuste fino.

## MultiDiffusion Integrated

Divide el lienzo en baldosas solapadas y muestrea cada una por separado, promediando en los solapes. Permite resoluciones que no caben de una pieza.

**Cuándo sí.** Para ampliar a 3–4K en img2img, donde ya hay una composición decidida y cada baldosa solo tiene que añadir detalle.

**Cuándo no.** Para txt2img directo. Ninguna baldosa ve la imagen completa, así que a resoluciones grandes se multiplican los sujetos y la composición se desarma. Y hay un motivo específico de tu máquina: con `--lowvram` el límite ya no es la VRAM de la baldosa sino el offload, así que pagas el coste de MultiDiffusion (muchas pasadas del modelo en vez de una) sin cobrar su beneficio principal.

**Valores.** Deja `Method` en **Mixture of Diffusers**, que es el default y da costuras mejores que MultiDiffusion clásico. Baldosas de 768×768 con `Tile Overlap` 64 es un punto de partida razonable; si ves costuras, sube el solape a 96 o 128 antes de tocar el tamaño. **`Tile Batch Size` déjalo en 1**: es el default y con 8 GB subirlo es la forma más rápida de provocar un OOM, porque multiplica las baldosas en vuelo simultáneas.

## Never OOM Integrated

Dos interruptores independientes que no tienen nada que ver entre sí más allá de evitar quedarse sin memoria.

**`Enabled for VAE (always tiled)`: actívalo y déjalo puesto.** Fuerza el decodificado del VAE por baldosas. El VAE es el punto donde más OOM ocurren, porque trabaja a resolución de píxel completa y no en el latente, y es justo lo que revienta al decodificar 2K o más después de un hires fix. El coste en calidad es prácticamente nulo y el de tiempo es pequeño. Para tu caso de 8 GB, es la recomendación más clara de todo este documento.

**`Enabled for UNet (always offload)`: no lo actives.** Pone el estado de memoria en `NO_VRAM`, que es un nivel más agresivo que el `--lowvram` con el que ya arrancas. Como ya estás descargando pesos y ya has comprobado que el offload es tu cuello de botella, esto solo añade lentitud. Además, al cambiar el interruptor descarga todos los modelos, así que la siguiente generación paga la recarga completa. Guárdalo para un caso extremo concreto, como un vídeo de Wan largo que no arranque de ninguna otra forma.

## ImageStitch Integrated

El nombre engaña y el propio script lo advierte: **no une imágenes**. Lo que hace es inyectar imágenes de referencia en el flujo de latentes, y su significado cambia según el modelo. De todos los scripts de esta lista, es el que más directamente se aplica a tu stack:

- **Flux.2 Klein**: en txt2img te permite partir de un latente vacío con la resolución que elijas; en img2img es **cómo se le dan varias imágenes de entrada a la vez**. Si has echado en falta el multi-imagen de Klein, está aquí.
- **Wan 2.2 I2V**: la imagen que cargues se usa como **último fotograma**. En txt2img eso te da "último fotograma a vídeo", y en img2img, combinado con la imagen de origen, te da "primer y último fotograma a vídeo", que es la forma de controlar dónde empieza y dónde acaba una animación.
- **Krea 2 Edit**: también está soportado, aunque para Krea 2 tienes las dos extensiones dedicadas que se describen a continuación.

**Cuándo no.** Con un modelo que no sea de edición o de imagen a vídeo no hace nada útil, porque nada en la arquitectura espera esos tokens de referencia.

**Valores.** No tiene apenas parámetros: es una galería de imágenes. Lo único que conviene recordar es el consejo del propio script, que puedes pegar imágenes desde el portapapeles con "Image to Upload".

## Krea2 Moodboard

Transferencia de estilo para Krea 2 sin entrenamiento: las imágenes de referencia se codifican con la torre de visión de Qwen3-VL-4B y se insertan en el condicionamiento como un único bloque de visión. Transfiere **paleta, luz, textura y ambiente, no sujetos ni composición**.

**Requisito que no es opcional**: necesitas el text encoder Qwen3-VL-4B **con pesos de visión** (`qwen3vl_4b_bf16.safetensors`) seleccionado junto al checkpoint de Krea 2. El log confirma `Detected Qwen3-VL-4B (vision) text encoder` cuando ha cargado bien. Sin eso, el acordeón no puede funcionar.

**Cuándo sí.** Cuando quieras que varias generaciones compartan un aire visual. Admite de 1 a 10 referencias y las mezcla en un único ambiente conjunto.

**Cuándo no.** Si lo que quieres es copiar un sujeto o una pose, este no es el sitio: para eso está Identity Edit. Y hay dos limitaciones que te pueden morder: **el énfasis de prompt `(...)` y la edición de prompt `[a:b:N]` no funcionan** junto con el moodboard, y las referencias solo afectan al prompt positivo.

**Valores.** El propio README trae una escalera de ajuste que vale la pena seguir tal cual:

| Objetivo | Extract | Strength | Posición | Procesado de ref. |
|---|---|---|---|---|
| Referencia cruda | cualquiera | 1.0 | before | full image |
| Sujeto, estilo por prompt | subject | 0.4–0.6 | before | full image |
| Estilo equilibrado | style | 0.6 | before | quadrants 2×2 |
| Ambiente tipo Krea | style | 0.5 | after | fine tiles 4×4 |
| Solo estilo, máximo | style | 0.4 | (forzado before) | fine tiles 4×4 + Indirect |

La fila de "ambiente tipo Krea" es la que más se parece a lo que hace krea.ai. La clave está en el procesado de referencia: `fine tiles (4x4)` trocea tanto la imagen que **los sujetos prácticamente no llegan a codificarse**, y es la solución real si se te está colando gente o objetos de las referencias. Ojo a una asimetría: el modo `subject` necesita `full image`, porque los recortes destruyen justamente lo que quieres conservar.

En Ajustes hay un `Vision encoder pixel budget`: **déjalo en 384**. La opción de 1024 sube a unos 1.024 tokens por imagen, y con varias referencias eso alarga el muestreo de forma notable, algo que en 8 GB se paga caro.

## Krea2 Identity Edit

Edición por instrucciones conservando la identidad, con LoRAs `krea2_edit` de la comunidad. Le das una imagen de origen y escribes la edición como prompt: *"create a photo of this person at a night market"* te devuelve la misma cara y la misma ropa, reiluminadas en la escena nueva.

Funciona por doble condicionamiento: la imagen pasa por el VAE y entra como tokens limpios en el fotograma 1 de RoPE mientras el objetivo es el fotograma 0, y en paralelo la instrucción se codifica *junto con* la imagen a través de Qwen3-VL, de modo que "el hombre de la izquierda" se resuelve contra la imagen real.

**Requisitos.** Checkpoint de Krea 2, el mismo text encoder con visión que el moodboard, y un LoRA `krea2_edit` **a fuerza 1.0** (se recomienda `krea2_identity_edit_v1_2`).

**Cuándo sí.** Es tu mejor herramienta para identidad en Krea 2, muy por encima de ReActor, por lo explicado antes: la identidad entra en el condicionamiento, no se pega al final.

**Cuándo no.** Sin el LoRA correcto no hace nada, porque toda la mecánica depende de que los pesos estén entrenados para preservar el contenido del fotograma 1.

**Valores.** La receta del autor del LoRA: para la mayoría de ediciones, turbo con 8 pasos y CFG 1; con el LoRA v1.2 puedes ir de 8 a 12 pasos, donde 8 favorece la composición y 12 el detalle de la cara. Para *eliminar* elementos, la receta cambia a Raw con 20 pasos y CFG 3. Genera a 2 MP o menos.

El parámetro que más vas a tocar es **`grounding_px`**, que empieza en 768: cuanto más bajo, más obedece a la instrucción; cuanto más alto, más se parece a la persona. Para retratos, sube a 1024 o más. En `Aspect ratio handling` usa **`fit source to output (v1.2)`** si trabajas con los pesos v1.2, porque es la geometría con la que se entrenaron y no introduce desenfoque; los modos `match source` y `crop source` son para v1/v1.1. `ref_boost` a 1.0 está desactivado; el autor sugiere entre 2 y 6 para tirar el resultado con más fuerza hacia la apariencia de la referencia.

Y una combinación que merece la pena conocer: **puedes activar Moodboard e Identity Edit a la vez** y obtienes identidad de la fuente de edición con estilo de las imágenes del moodboard. La configuración recomendada del moodboard para ese caso es extract `style`, `full image`, Indirect activado y directiva activada.

## Spectrum Integrated

Predice el resultado de los pasos intermedios con un ajuste polinómico del historial en vez de ejecutar el modelo completo, y así se salta pasos. Es la misma familia de trucos que TeaCache.

**No lo uses con turbo.** Y el motivo se ve en los propios defaults: `Warmup Steps` vale 6 y `Stop Caching Step` vale 0.9. Con 8 pasos totales, los 6 primeros van completos por el calentamiento y el último va completo porque el 0.9 reserva el tramo final, así que **queda un paso, o ninguno, donde aplicar la caché**. El mecanismo no tiene margen. En el mejor caso no notarás nada, y si fuerzas los parámetros para que actúe, estarás prediciendo pasos en un muestreo donde cada paso vale un octavo del resultado, que es exactamente donde más se nota un error de predicción.

**Cuándo podría servir.** Solo en Wan 2.2 con muchos pasos, o en vídeos largos, donde hay suficientes pasos como para que saltarse algunos ahorre de verdad. Si lo pruebas ahí, baja `Warmup Steps` a 2 o 3, deja `Cache Window` en 2 y `Window Growth` en 0, y compara siempre contra una generación sin Spectrum con la misma semilla. Con `Polynomial Degree` alto (el default es 6) el ajuste captura patrones más sutiles pero es menos estable; bajarlo a 3 o 4 es más conservador.

## Torch Compile Integrated

Compila el modelo con `torch.compile` e Inductor para acelerar la inferencia. El acordeón solo aparece si Triton está disponible, que en esta imagen lo está (por eso se añadieron `gcc` y `g++` al runtime, porque Triton los necesita para compilar en caliente).

**Aquí está el detalle que te afecta directamente: `max-autotune` y `reduce-overhead` no funcionan con `--cuda-malloc`, y tú lo tienes activo.** No es que rindan peor: el script los rechaza, escribe un error en el log y deja el modelo sin compilar. Te quedan tres presets utilizables:

| Preset | Qué da | Coste |
|---|---|---|
| `guard_filter_fn` | La compilación más rápida de ejecutar | Recompila si cambias resolución o batch |
| `dynamic` | Cualquier resolución y batch sin recompilar | Tarda más en compilar |
| `max-autotune-no-cudagraphs` | Más rápido que `dynamic`, cualquier resolución | El que más tarda en compilar |

**Cuándo sí.** Para lotes largos a resolución fija, que en tu caso es sobre todo Wan. Ahí compilas una vez y amortizas el coste a lo largo de muchos pasos.

**Cuándo no.** Para uso interactivo cambiando de resolución y de modelo. Cada recompilación cuesta minutos, y con `--lowvram` el offload sigue dominando el tiempo total, así que aceleras la parte que menos pesa. Si además vas cambiando de checkpoint entre Klein, Krea 2 y Wan, pagarás la compilación una y otra vez.

**Valores.** Si lo pruebas, empieza por `guard_filter_fn` con la resolución ya decidida. Recuerda que **`Automatic`, que es el default, no significa "no compilar": significa "mantener el estado actual"**, así que si has compilado y quieres deshacerlo tienes que elegir `Disable` explícitamente. Si algún día quieres medir `max-autotune`, tendrás que quitar `--cuda-malloc` de `EXTRA_ARGS` y aceptar el peor comportamiento de asignación de memoria que ese flag te estaba evitando; en 8 GB, ese cambio probablemente no te salga a cuenta.

---

## Un par de combinaciones a evitar

**Sparse Attention junto con `make wan`.** El perfil `make wan` activa la atención INT8 de Comfy-Kitchen mediante `--use-ck-attention`, y Sparse Attention instala un override que la sustituye. Elige una.

**MultiDiffusion junto con Never OOM de UNet.** Son dos estrategias de ahorro de memoria que se estorban: MultiDiffusion trocea para que quepa, y `NO_VRAM` descarga pesos en cada baldosa. El resultado es lentísimo.

**Hires fix a 2× sin el VAE tiled.** La combinación que más OOM provoca en 8 GB. Si vas a ampliar, ten el VAE tiled de Never OOM activado.
