# Voice Changer RT

Cambiador de voz en tiempo real para Windows. Toma tu micrófono, te cambia la voz (más gruesa o más fina, como frenar o acelerar una grabación, y/o más grave o más aguda) sin atrasar lo que decís, y manda el resultado a un **cable de audio virtual**. Discord, Zoom, OBS, etc. lo ven como si fuera un micrófono.

```
Micrófono físico ──► Voice Changer RT ──► CABLE Input ══(VB-CABLE)══► CABLE Output ──► Discord / Zoom
                     (efecto o bypass)                                 (lo elegís como micrófono)
```

Qué trae:

- **Panel principal "Voz modificada / Voz normal"** (efecto activo o bypass): verde = voz modificada, grafito = voz normal. Se alterna con clic, Espacio/Enter o el atajo. El audio cambia con un fundido de ~5 ms, así no hace "click".
- **Atajo de teclado global** que funciona con la ventana minimizada o en segundo plano. Se puede configurar y tiene dos modos:
  - **Alternar**: cada pulsación prende o apaga el efecto.
  - **Mantener**: el efecto funciona sólo mientras mantenés la tecla (estilo push-to-talk).
- **Velocidad** de 0,5× a 1,5×: suena como reproducir tu voz más lenta (más **gruesa**) o más rápida (más **fina**), pero en vivo y sin atrasarse.
- **Tono** de −12 a +12 semitonos: cambia la nota y **conserva tu timbre**.
- Botones **Original** y **Voz 0.7×** (el efecto de un audio a 0,7×).
- Selector de **driver de Windows**, **micrófono** y **salida**. VB-CABLE se detecta solo.
- **Medidor del micrófono en dB**, control de volumen y **retraso estimado** en vivo.
- La configuración se guarda sola en `config.json`.

---

## 1. Estructura del proyecto

```
app voicemod/
├── main.py                    ← punto de entrada (abre la ventana)
├── iniciar.bat                ← doble clic: instala todo la 1ª vez y abre la app
├── build_exe.bat              ← genera dist\VoiceChangerRT.exe (versión portable)
├── requirements.txt           ← dependencias de Python
├── config.json                ← (se crea solo) última configuración usada
├── voicechanger/
│   ├── __init__.py
│   ├── tape_speed.py          ← Velocidad tipo cinta (WSOLA + remuestreo)
│   ├── pitch_shifter.py       ← Tono (phase vocoder que conserva formantes)
│   ├── audio_engine.py        ← streams de audio, bypass, buffer y compensación de deriva
│   ├── devices.py             ← listado de dispositivos y detección del cable virtual
│   ├── hotkey.py              ← atajo de teclado global (pynput)
│   ├── config.py              ← guardar / cargar config.json
│   ├── gui.py                 ← interfaz (CustomTkinter)
│   ├── widgets.py             ← panel principal, medidor en dB y punto "en vivo"
│   ├── motion.py              ← animaciones cortas (respeta "Mostrar animaciones" de Windows)
│   ├── theme.py               ← colores y tipografía
│   └── assets/fonts/          ← (opcional, no incluida) tipografía ZT Nature, ver 3.4
```

## 2. Tecnologías elegidas y por qué

| Pieza | Elección | Motivo |
|---|---|---|
| Lenguaje | **Python 3.10+** | Rápido de modificar. NumPy hace las FFT en C, así que el procesamiento usa ~2-4 % de CPU. |
| Audio I/O | **sounddevice** (PortAudio) | Da acceso a WASAPI (incluso en modo exclusivo) y a WDM-KS, que son los drivers de baja latencia de Windows. PyAudio no expone las opciones de WASAPI. |
| DSP | **NumPy** (algoritmo propio) | Librosa no sirve para tiempo real: procesa archivos enteros y tiene mucha latencia. Acá el algoritmo trabaja de a 256 muestras. |
| GUI | **CustomTkinter** | Se ve moderna, viene casi todo con Python y no necesita navegador. |
| Atajo global | **pynput** | Hook de teclado de Windows. No necesita permisos de administrador y no bloquea las teclas. |

**Alternativas.** C# + NAudio o C++ + JUCE consiguen menos latencia (~10-20 ms) y se distribuyen como un `.exe`, pero son bastante más código. Electron/Node no conviene: el audio de baja latencia en Node depende de módulos nativos frágiles. Si después querés un ejecutable de este proyecto, `pyinstaller --noconsole main.py` lo genera.

---

## 3. Instalación

### 3.1 Python

Instalá Python 3.10 o superior desde <https://www.python.org/downloads/>. En el instalador marcá **"Add Python to PATH"**.

### 3.2 Driver de audio virtual: VB-CABLE (gratis)

1. Entrá a <https://vb-audio.com/Cable/> y descargá **"VBCABLE_Driver_Pack"** (ZIP).
2. Descomprimí el ZIP en una carpeta.
3. Clic derecho sobre **`VBCABLE_Setup_x64.exe`** → **Ejecutar como administrador** → **Install Driver**.
4. **Reiniciá la PC.**
5. Ahora Windows tiene dos dispositivos nuevos:
   - **CABLE Input** (dispositivo de *salida*): acá escribe esta app.
   - **CABLE Output** (dispositivo de *entrada* / micrófono): esto es lo que eligen Discord, Zoom, etc.
6. *(Recomendado)* Poné el cable a 48 kHz para que coincida con la app. En *Panel de control → Sonido*, buscá **CABLE Input** en *Reproducción* y **CABLE Output** en *Grabación*. En cada uno: *Propiedades → Opciones avanzadas → 2 canales, 24 bits, 48000 Hz*.

> Alternativas: **VoiceMeeter** (del mismo autor, incluye cables virtuales) o **Virtual Audio Cable** (pago). Funcionan igual: elegí su entrada ("Input"/"Line 1") como salida de la app.

### 3.3 Dependencias de la app

**Opción fácil:** doble clic en **`iniciar.bat`**. La primera vez crea un entorno virtual (`.venv`) e instala todo; las siguientes sólo abre la app.

**Opción manual** (PowerShell, dentro de la carpeta del proyecto):

```bash
python -m venv .venv
```

```bash
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

```bash
.venv\Scripts\python.exe main.py
```

### 3.4 Versión portable (.exe)

`dist\VoiceChangerRT.exe` es un único archivo que no necesita Python ni instalación: copialo a cualquier carpeta o pendrive y abrilo. La configuración se guarda en `config.json` al lado del exe. La PC donde lo uses igual necesita **VB-CABLE** instalado (punto 3.2), porque es un driver de Windows.

- La primera vez puede tardar unos segundos en abrir (se descomprime y Windows Defender lo revisa).
- Como no está firmado digitalmente, SmartScreen puede mostrar "Windows protegió su PC": *Más información → Ejecutar de todas formas*.

Para regenerarlo después de cambiar el código, doble clic en **`build_exe.bat`** (usa PyInstaller y deja el resultado en `dist\`).

La tipografía **ZT Nature** no está en el repositorio: su licencia (1001Fonts FFC) permite incrustarla en una aplicación, pero no publicarla como descarga. Para usarla, descargala de 1001fonts.com y copiá `ZTNature-Regular.otf` y `ZTNature-Bold.otf` en `voicechanger\assets\fonts\`; `build_exe.bat` la incluye en el exe si la encuentra. Sin ella, la app usa Segoe UI.

---

## 4. Configuración

### 4.1 En la app

1. **Driver de audio**: dejá **Windows WASAPI**. Es el que mejor anda (ver la tabla de latencias).
2. **Micrófono**: tu micrófono físico.
3. **Enviar la voz a**: **CABLE Input (VB-Audio Virtual Cable)**. La app la elige sola si la encuentra, y el aviso de abajo dice «Listo».
4. **Iniciar audio** (arriba a la derecha). El punto se pone verde y dice «En vivo».
5. En **Efecto de voz** mové **Velocidad** (0,7× = más gruesa) y/o **Tono**, o tocá **Voz 0.7×**. Activá o desactivá el efecto con el panel grande o con el atajo.

> Al instalar VB-CABLE, Windows suele poner **CABLE Output** como micrófono predeterminado. La app lo saltea y elige tu micrófono real; si igual lo elegís a mano, te avisa: usarlo armaría un bucle (la app escuchándose a sí misma) que suena metálico.

### 4.2 Atajo de teclado

- Por defecto es **F8**. Para cambiarlo, tocá **Cambiar**, presioná la tecla o combinación (por ejemplo `Ctrl + Shift + V`) y soltala. **Cancelar** o **Esc** dejan el atajo anterior.
- Elegí el modo: **Alternar** o **Mantener**.
- Funciona aunque la ventana esté minimizada. Las teclas no se bloquean: el juego o programa que tengas enfocado también las recibe. Elegí una tecla que no uses para otra cosa.

### 4.3 En Discord / Zoom / OBS

- **Discord**: *Configuración → Voz y video → Dispositivo de entrada* → **CABLE Output (VB-Audio Virtual Cable)**.
  Conviene desactivar *Supresión de ruido (Krisp)* y *Control automático de ganancia*: confunden la voz modificada con ruido.
- **Zoom**: *Configuración → Audio → Micrófono* → **CABLE Output**.
- **OBS**: agregá una fuente *Captura de entrada de audio* con **CABLE Output**.

### 4.4 Escucharte a vos mismo (opcional)

*Panel de control → Sonido → Grabación* → **CABLE Output** → *Propiedades → Escuchar* → marcá **"Escuchar este dispositivo"** y elegí tus auriculares. Esto suma la latencia de Windows: sirve para probar el tono, pero no para hablar escuchándote.

---

## 5. Cómo mapear los dispositivos en el código

Normalmente no hace falta tocar nada: todo se elige desde la GUI y se guarda en `config.json` (por **nombre**, porque los números de dispositivo cambian al enchufar cosas). Si querés cambiar los valores por defecto:

| Qué | Dónde |
|---|---|
| Palabras con las que se detecta el cable virtual (`"CABLE Input"`, `"VB-Audio"`, `"Line 1"`…) | `voicechanger/devices.py` → `VIRTUAL_CABLE_HINTS` |
| Orden de preferencia de drivers (WASAPI → MME → DirectSound) | `voicechanger/devices.py` → `PREFERRED_HOSTAPIS` |
| Frecuencia de muestreo y tamaño de bloque | `voicechanger/audio_engine.py` → `SAMPLERATE = 48_000`, `BLOCKSIZE = 256` |
| Atajo y modo por defecto | `voicechanger/config.py` → `"hotkey": [119]` (códigos VK de Windows; 119 = F8) y `"hotkey_mode"` |

Para usar el motor **sin GUI** (por ejemplo, desde otro script):

```python
from voicechanger.audio_engine import AudioEngine

engine = AudioEngine()
engine.set_semitones(-4)            # voz más grave
engine.start("Windows WASAPI",
             "Micrófono (Realtek(R) Audio)",           # nombre exacto del mic
             "CABLE Input (VB-Audio Virtual Cable)")   # nombre exacto del cable
engine.effect_active = False        # bypass
```

Para ver los nombres exactos de tus dispositivos:

```bash
.venv\Scripts\python.exe -m sounddevice
```

---

## 6. Cómo funciona, paso a paso

### 6.1 Flujo de audio (`audio_engine.py`)

1. **InputStream** (micrófono) entrega bloques de 256 muestras (~5 ms) a un *callback* que corre en un hilo de audio de alta prioridad.
2. El bloque se pasa a mono y se calcula el nivel para el vúmetro.
3. Se procesa con la cadena **Tono → Velocidad**. Tono se saltea si está en 0 y Velocidad si está en 1×, así no suman retraso ni artefactos. Los efectos se alimentan **siempre**, aunque estés en bypass: al activarlos ya tienen sus buffers llenos y el cambio es inmediato.
4. Según el estado del toggle se usa la señal original (*dry*) o la procesada (*wet*). Si el estado cambió en ese bloque, se hace un fundido lineal entre las dos.
5. Se aplica el volumen y se recorta a [−1, 1].
6. El resultado va a un **buffer circular** (`RingBuffer`).
7. **OutputStream** (CABLE Input) lee del buffer y copia la señal a los canales L y R.

Entrada y salida son **dos streams separados** porque son dispositivos distintos con relojes distintos. El micrófono puede ir a 48 010 Hz y el cable a 47 995 Hz. Sin corrección, con el tiempo el buffer se llenaría (más latencia) o se vaciaría (cortes). Por eso el `RingBuffer`:

- **Compensa la deriva**: cada ~0,25 s mira cuánto sobró como mínimo tras cada lectura, lo promedia y ajusta la velocidad de lectura de a poco (en ~4 s, como máximo ±0,3 %), remuestreando el bloque. Es inaudible y no hace temblar la voz.
- Tiene un **margen adaptativo** que arranca en ~5 ms (los micrófonos inalámbricos entregan el audio en ráfagas): si igual se vacía, el margen crece hasta que deja de cortarse.
- **Descarta excedentes** grandes, por ejemplo las ráfagas al arrancar.

### 6.2 Tono (`pitch_shifter.py`)

Es un **phase vocoder** con desplazamiento por regiones de pico (método de Laroche y Dolson):

1. Ventana de **N = 1024** muestras que avanza de a **256** (solapamiento del 75 %), con ventana de Hann.
2. **FFT** → magnitud y fase de cada frecuencia ("bin").
3. Comparando la fase con la de la ventana anterior se calcula la **frecuencia real** de cada componente.
4. Se buscan los **picos** (los armónicos de la voz) y cada bin se asigna al pico más cercano.
5. Cada región se **mueve entera** a `pico × 2^(semitonos/12)` y se le **gira la fase** para que suene a la nueva frecuencia. Mover la región completa conserva la forma de cada armónico, por eso suena menos metálico que el método clásico bin por bin.
6. **Conserva el timbre**: con el *cepstrum* se calcula la envolvente espectral (la forma de los formantes) y cada armónico movido toma el volumen que esa envolvente tiene en su nuevo lugar. Cambia la nota, pero la voz no suena "más chica" ni "más grande".
7. **FFT inversa** y suma de ventanas solapadas (*overlap-add*).

La cantidad de ventanas por segundo no cambia, así que **la duración y la velocidad del habla se mantienen** y sólo cambia el tono. El algoritmo agrega `N − 256` muestras de retardo: 8 ms con N = 512, 16 ms con N = 1024 y 32 ms con N = 2048. Lo elegís en *Ajustes → Calidad del efecto* (Rápida = 512, Equilibrada = 1024, Natural = 2048).

### 6.3 Velocidad (`tape_speed.py`)

Imita una cinta o un video a otra velocidad: 0,7× baja el tono **y** los formantes juntos, por eso la voz suena más gruesa (y a 1,3× más fina). Todo en el dominio del tiempo, sin FFT, por eso suena natural.

1. **Remuestreo**: leer el audio a 0,7× cambia tono y timbre, pero también estiraría la duración, y en vivo no podés quedar atrasado.
2. **WSOLA** (*Waveform Similarity Overlap-Add*): antes de remuestrear, la duración se ajusta en sentido contrario repitiendo o salteando fragmentos de 21 ms. Cada fragmento se elige (±5 ms) donde la forma de onda empalma mejor con el anterior, así no hay saltos.
3. Resultado: el tono y el timbre cambian, y las palabras salen al mismo ritmo en que las decís. Suma ~27 ms de retraso.

En vivo no se puede **hablar más lento** de verdad: la voz se iría atrasando cada vez más (unos 3 s por cada 10 s de habla).

### 6.4 Atajo global (`hotkey.py`)

`pynput` instala un hook de teclado de Windows que avisa cada tecla presionada o soltada en cualquier programa. La app lleva la cuenta de qué teclas están apretadas:

- Cuando se completa la combinación, llama a `on_press` **una sola vez**: la autorepetición de Windows al mantener la tecla se ignora.
- Cuando se suelta una tecla de la combinación, llama a `on_release`.
- **Alternar** invierte el estado en `on_press`. **Mantener presionado** activa en `on_press` y desactiva en `on_release`.

Los callbacks corren en el hilo de pynput: sólo cambian `engine.effect_active`, y la ventana se actualiza sola 20 veces por segundo.

---

## 7. Latencia

Valores estimados por la app con un headset inalámbrico y VB-CABLE, con **Velocidad 0,7×**:

| Driver | Retraso con efecto | Notas |
|---|---|---|
| **WASAPI exclusivo** | **~75 ms** | El más rápido. La app toma el dispositivo en exclusiva. Si el dispositivo no lo soporta bien, la app pasa sola a compartido y te avisa. |
| WASAPI compartido | ~100 ms | El más compatible. Windows suma ~20 ms por lado. |
| WDM-KS | ~75 ms (no medido con VB-CABLE) | Muy bajo, pero con algunos drivers es inestable. |
| DirectSound / MME | ~150-200 ms | Sólo como último recurso. |

Cada efecto suma lo suyo sólo cuando está en uso: Velocidad ~27 ms y Tono ~16 ms (con *Calidad: Equilibrada*). En **bypass** no suman nada.

Para bajar más la latencia: usá WASAPI exclusivo, poné el cable a 48 kHz (punto 3.2.6), elegí *Calidad del efecto: Rápida* (suena un poco más robótica) y usá micrófonos con cable antes que inalámbricos.

---

## 8. Problemas comunes

| Síntoma | Solución |
|---|---|
| "No encontramos un cable virtual" | Instalá VB-CABLE, reiniciá y tocá **Actualizar dispositivos** en la app. |
| Discord no escucha nada | En Discord el micrófono tiene que ser **CABLE Output**, y en la app la salida tiene que ser **CABLE Input**. Revisá que el vúmetro se mueva. |
| "No se pudo iniciar" | Otro programa está usando el micrófono o la salida en modo exclusivo. Cerralo o destildá *Modo exclusivo*. |
| Cortes o chasquidos ("Hay cortes en el audio") | Destildá *Modo exclusivo* o probá otro driver de audio. |
| Te suena robótico o metálico cuando **te escuchás** | Si te escuchás en los auriculares con 50-100 ms de atraso, tu voz procesada se mezcla con la que oís por dentro de la cabeza y suena metálica. La gente en Discord no oye eso. Para juzgar el efecto, grabate (por ejemplo con la Grabadora de Windows usando **CABLE Output**) y escuchá la grabación. |
| La voz suena "metálica" en la grabación | Pasa con Tono en cambios grandes (más de ±7 semitonos). Para voz más gruesa o más fina usá **Velocidad**, que suena más natural. *Calidad del efecto: Natural* también mejora el Tono, con más retraso. |
| "El micrófono elegido es el cable virtual" | En «Micrófono» elegí tu micrófono real, no **CABLE Output**: si no, la app se escucharía a sí misma. |
| El atajo no funciona en un juego | Si el juego corre **como administrador**, Windows no deja que una app normal lea su teclado. Ejecutá también esta app como administrador. |
| Me escucho con eco en Discord | Desactivá "Escuchar este dispositivo" (punto 4.4) mientras hablás. |
