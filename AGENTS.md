# AGENTS.md - IndexTTS

## Project Overview

IndexTTS2 is a GPT-based autoregressive zero-shot text-to-speech system by Bilibili. It uses PyTorch, supports Chinese and English, and provides emotion control via vectors, reference audio, or text descriptions.

- Python 3.10+, managed with **uv** (not pip)
- Package manager: `uv` with `pyproject.toml` and `uv.lock`
- Main entry: `indextts/infer.py` (v1) and `indextts/infer_v2.py` (v2)
- CLI: `indextts/cli.py` (installed via `indextts` command)
- WebUI: `webui.py` (Gradio-based)

## Build & Setup

```bash
# Install dependencies
uv sync

# Install with optional extras
uv sync --extra webui        # Gradio WebUI support
uv sync --extra deepspeed    # DeepSpeed acceleration
uv sync --all-extras         # Everything

# Install as CLI tool
uv tool install -e .
```

After editing dependencies in `pyproject.toml`, always run:
```bash
uv lock          # or uv lock --upgrade
```

## Running the Project

```bash
# CLI inference
indextts -v voice.wav -o output.wav "Text to synthesize"

# WebUI
python webui.py --model_dir checkpoints

# Direct Python inference
python -c "from indextts.infer import IndexTTS; tts = IndexTTS(...); tts.infer(...)"
```

## Tests

Tests are standalone scripts (no pytest). Run directly:

```bash
# Regression test (requires checkpoints/ directory)
python tests/regression_test.py

# Padding test
python tests/padding_test.py checkpoints
python tests/padding_test.py IndexTTS-1.5
```

There is no formal test framework, no pytest configuration, and no CI test pipeline. Tests require model checkpoints in `checkpoints/` and `tests/sample_prompt.wav`.

## Code Style

### General
- No formatter or linter is configured (ruff cache is gitignored but no `ruff.toml` or `[tool.ruff]` exists)
- No type checker (mypy) is configured
- Indent: 4 spaces
- Line length: no strict limit, but keep under ~120 chars

### Imports
- Standard library first, then third-party, then local (`indextts.*`)
- Common pattern: `import os` at top, sometimes with `os.environ` setup immediately after
- Suppress library warnings at module top:
  ```python
  import warnings
  warnings.filterwarnings("ignore", category=FutureWarning)
  warnings.filterwarnings("ignore", category=UserWarning)
  ```

### Naming
- Classes: `PascalCase` (`IndexTTS`, `IndexTTS2`, `TextNormalizer`, `QwenEmotion`)
- Functions/methods: `snake_case` (`infer`, `infer_fast`, `remove_long_silence`)
- Private methods: `_prefix` (`_set_gr_progress`, `_load_and_cut_audio`)
- Constants: not strictly enforced
- Files: `snake_case` (`infer_v2.py`, `feature_extractors.py`)

### Types
- Type hints used sparingly, mainly in function signatures for complex types:
  ```python
  def bucket_segments(self, segments, bucket_max_size=4) -> List[List[Dict]]:
  def pad_tokens_cat(self, tokens: List[torch.Tensor]) -> torch.Tensor:
  ```
- Import typing constructs from `typing`: `List`, `Dict`, `Union`, `Optional`

### Error Handling
- Graceful fallbacks for optional dependencies (DeepSpeed, CUDA kernels):
  ```python
  try:
      import deepspeed
  except (ImportError, OSError, CalledProcessError) as e:
      use_deepspeed = False
      print(f">> Failed to load DeepSpeed. Falling back... Error: {e}")
  ```
- Use `print(">> ...")` prefix for status messages
- Use `warnings.warn(...)` with `category=RuntimeWarning` for non-fatal issues
- CLI uses `sys.exit(1)` with `print("ERROR: ...")` for fatal errors

### Comments & Docs
- Bilingual: Chinese comments are common alongside English code
- Docstrings: used in some classes/methods, not consistently
- Inline comments explain "why", not "what"

### PyTorch Conventions
- Device handling: check CUDA → XPU → MPS → CPU in order
- FP16: `self.dtype = torch.float16 if self.use_fp16 else None`
- Autocast: `torch.amp.autocast(device_type, enabled=..., dtype=...)`
- Move to CPU before saving: `wav.cpu()`
- Clear GPU cache: `torch.cuda.empty_cache()`

## Directory Structure

```
indextts/
├── __init__.py          # empty
├── infer.py             # IndexTTS v1 inference
├── infer_v2.py          # IndexTTS2 inference + QwenEmotion
├── cli.py               # CLI entry point
├── gpt/                 # GPT model implementations
├── BigVGAN/             # Vocoder (v1)
├── s2mel/               # Vocoder pipeline (v2): BigVGAN, CAMPPlus, flow matching
├── vqvae/               # Discrete VAE tokenizer
├── utils/               # Text processing, checkpoints, feature extractors
│   ├── front.py         # TextNormalizer, TextTokenizer
│   ├── checkpoint.py    # load_checkpoint
│   └── maskgct/         # Semantic model (MaskGCT)
├── accel/               # GPT2 acceleration (KV cache, attention)
tools/                   # GPU check, i18n utilities
tests/                   # Standalone test scripts
webui.py                 # Gradio WebUI
```

## Key Conventions

- Model configs loaded via `omegaconf.OmegaConf.load(cfg_path)`
- Checkpoints expected in `checkpoints/` directory with `config.yaml`
- Audio: torchaudio for load/save, librosa for some loading, 22050/24000 Hz sample rates
- Tokenizers: `sentencepiece` BPE models
- HuggingFace Hub: used for downloading pretrained models (`hf_hub_download`)
