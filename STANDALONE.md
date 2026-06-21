# Standalone RMBG-2-Studio Technical Documentation

This document explains the technical details of running RMBG-2-Studio without the Pinokio orchestration platform.

## Architecture

The project consists of:
1. **Frontend/Backend**: A single-file Gradio application (`app/app.py`).
2. **Model**: BRIA-RMBG-2.0 (BiRefNet architecture).
3. **Environment Management**: Scripts (`setup.bat`, `run.bat`, etc.) that handle dependencies.

## Dependency Management

To solve the significant version conflict issues between Gradio 4.x and modern AI libraries, we use strict version pinning in `app/requirements.txt`:

| Package | Version | Reason |
|---------|---------|--------|
| `gradio` | `4.44.0` | Pin for `gradio_imageslider` compatibility. |
| `gradio_client` | `1.3.0` | Matches Gradio 4.44.0 exactly. |
| `huggingface-hub` | `0.26.2` | Prevents `ImportError: HfFolder` found in newer versions. |
| `numpy` | `1.26.4` | Version 2.0+ breaks many legacy AI libraries. |
| `fsspec` | `2024.10.0` | Required for compatibility with pinned HF and Gradio. |
| `pydantic` | `2.10.6` | Prevents serialization errors in newer Pydantic versions. |

## Monkeypatching

Due to a known bug in `gradio_client` (and specifically its interaction with newer `pydantic` types), `app.py` includes a monkeypatch at the very top:

```python
import gradio_client.utils
_old_get_type = gradio_client.utils.get_type
def _patched_get_type(schema):
    if isinstance(schema, bool):
        return "boolean"
    return _old_get_type(schema)
gradio_client.utils.get_type = _patched_get_type
```

This fix prevents the `TypeError: argument of type 'bool' is not iterable` crash during app startup without requiring users to download additional patches.

## GPU Support

The setup scripts automatically detect your hardware:
- **Windows NVIDIA**: Installs Torch with CUDA 12.4 support (`cu124`).
- **Mac (M1/M2/M3)**: Installs Torch with Metal Performance Shaders (MPS) support.
- **Linux NVIDIA**: Installs Torch with CUDA 12.4.
- **Linux AMD**: Installs Torch with ROCm 6.2.4.

## Manual Maintenance

If you need to update the model or dependencies:
1. Modify `app/requirements.txt`.
2. Delete the `app/env` folder.
3. Run `setup.bat` again.
