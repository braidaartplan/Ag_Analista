import json
from pathlib import Path
import streamlit.components.v1 as components

# Resolve o diretório do frontend de forma robusta
try:
    # Python 3.9+: funciona quando o pacote estiver instalado
    from importlib.resources import files
    FRONTEND_DIR = files(__package__) / "frontend"
    FRONTEND_PATH = str(FRONTEND_DIR)
except Exception:
    # fallback: relativo ao arquivo atual (uso local)
    FRONTEND_PATH = str(Path(__file__).parent / "frontend")

# Sanidade: falha amigável se não existir
if not Path(FRONTEND_PATH).exists():
    raise FileNotFoundError(f"[custom_uploader] Frontend não encontrado em: {FRONTEND_PATH}")

_component_func = components.declare_component(
    "custom_uploader",
    path=FRONTEND_PATH
)

def custom_uploader(
    label: str = "Upload file",
    key: str | None = None,
    multiple: bool = False,
    accept: list[str] | None = None
):
    """
    Botão de upload custom (sem a caixa do Streamlit).
    Retorna:
      - None (sem seleção)
      - dict(name,type,size,base64) quando multiple=False
      - list[dict] quando multiple=True
    """
    accept = accept or []
    return _component_func(
        label=label,
        multiple=multiple,
        accept=json.dumps(accept),
        key=key,
        default=None
    )
