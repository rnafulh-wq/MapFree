"""
Workspace state persistence for auto-resume.
Tracks pipeline step completion and per-chunk progress via .mapfree_state.json.
Does not know engine output layout; use validation.py for output checks.
"""
import json
from pathlib import Path

from .config import PIPELINE_STEPS, CHUNK_STEPS

STATE_FILE = ".mapfree_state.json"

# Default state: one bool per pipeline step + chunks dict
DEFAULT_STATE = {step: False for step in PIPELINE_STEPS}
DEFAULT_STATE["chunks"] = {}


def _state_path(workspace_path):
    return Path(workspace_path) / STATE_FILE


def _normalize_chunk(c):
    """Ensure chunk entry has keys from CHUNK_STEPS."""
    if not isinstance(c, dict):
        return {s: False for s in CHUNK_STEPS}
    return {s: bool(c.get(s, False)) for s in CHUNK_STEPS}


def load_state(workspace_path):
    p = _state_path(workspace_path)
    if p.exists():
        try:
            with open(p, "r") as f:
                data = json.load(f)
            for k in DEFAULT_STATE:
                if k not in data:
                    data[k] = False if k != "chunks" else {}
            chunks = data.get("chunks")
            if not isinstance(chunks, dict):
                chunks = {}
            # Backward compat: migrate chunk_sparse_done -> chunks
            legacy = data.get("chunk_sparse_done")
            if isinstance(legacy, list) and legacy:
                for name in legacy:
                    if name and name not in chunks:
                        chunks[name] = {s: True for s in CHUNK_STEPS}
                if "chunk_sparse_done" in data:
                    del data["chunk_sparse_done"]
            data["chunks"] = {k: _normalize_chunk(v) for k, v in chunks.items()}
            return data
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_STATE)


def save_state(workspace_path, state_dict):
    p = _state_path(workspace_path)
    Path(workspace_path).mkdir(parents=True, exist_ok=True)
    with open(p, "w") as f:
        json.dump(state_dict, f, indent=2)


def mark_step_done(workspace_path, step_name):
    s = load_state(workspace_path)
    s[step_name] = True
    save_state(workspace_path, s)


def is_step_done(workspace_path, step_name):
    return load_state(workspace_path).get(step_name, False)


def get_chunk_state(workspace_path, chunk_name):
    """Return per-chunk state dict (keys from CHUNK_STEPS)."""
    s = load_state(workspace_path)
    chunks = s.get("chunks") or {}
    return _normalize_chunk(chunks.get(chunk_name))


def is_chunk_step_done(workspace_path, chunk_name, step_name):
    if step_name not in CHUNK_STEPS:
        return False
    return get_chunk_state(workspace_path, chunk_name).get(step_name, False)


def is_chunk_mapping_done(workspace_path, chunk_name):
    return is_chunk_step_done(workspace_path, chunk_name, "mapping")


def mark_chunk_step_done(workspace_path, chunk_name, step_name):
    if step_name not in CHUNK_STEPS:
        return
    s = load_state(workspace_path)
    s["chunks"] = s.get("chunks") or {}
    s["chunks"][chunk_name] = _normalize_chunk(s["chunks"].get(chunk_name))
    s["chunks"][chunk_name][step_name] = True
    save_state(workspace_path, s)


def reset_state(workspace_path):
    p = _state_path(workspace_path)
    if p.exists():
        p.unlink()
