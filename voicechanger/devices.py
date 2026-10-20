import sounddevice as sd

PREFERRED_HOSTAPIS = ("Windows WASAPI", "MME", "Windows DirectSound")

VIRTUAL_CABLE_HINTS = ("CABLE Input", "VB-Audio", "Virtual Audio Cable", "Line 1", "Virtual")


def list_hostapis() -> list[str]:
    return [h["name"] for h in sd.query_hostapis()]


def default_hostapi() -> str:
    names = list_hostapis()
    for preferred in PREFERRED_HOSTAPIS:
        if preferred in names:
            return preferred
    return names[0]


def _hostapi_index(hostapi_name: str) -> int:
    for i, h in enumerate(sd.query_hostapis()):
        if h["name"] == hostapi_name:
            return i
    raise ValueError(f"Host API no encontrada: {hostapi_name}")


def list_devices(hostapi_name: str, kind: str) -> list[tuple[int, str]]:
    api = _hostapi_index(hostapi_name)
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    return [
        (i, d["name"])
        for i, d in enumerate(sd.query_devices())
        if d["hostapi"] == api and d[key] > 0
    ]


def default_device_name(hostapi_name: str, kind: str) -> str | None:
    h = sd.query_hostapis(_hostapi_index(hostapi_name))
    idx = h["default_input_device"] if kind == "input" else h["default_output_device"]
    return sd.query_devices(idx)["name"] if idx >= 0 else None


def is_virtual(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in ("cable", "vb-audio", "virtual", "voicemeeter"))


def _is_alias_or_mixer(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in (
        "asignador", "mapper", "controlador primario", "primary sound", "mixline",
        "mezcla estéreo", "stereo mix",
    ))


def pick_microphone(input_names: list[str], preferred: list[str | None]) -> str | None:
    real = [name for name in input_names if not is_virtual(name) and not _is_alias_or_mixer(name)]
    for name in preferred:
        if name in real:
            return name
    return real[0] if real else (input_names[0] if input_names else None)


def find_virtual_cable(output_names: list[str]) -> str | None:
    for hint in VIRTUAL_CABLE_HINTS:
        for name in output_names:
            if hint.lower() in name.lower():
                return name
    return None


def device_index(hostapi_name: str, kind: str, name: str) -> int:
    for idx, dev_name in list_devices(hostapi_name, kind):
        if dev_name == name:
            return idx
    raise ValueError(f"Dispositivo no encontrado: {name}")


def is_wasapi(hostapi_name: str) -> bool:
    return "WASAPI" in hostapi_name
