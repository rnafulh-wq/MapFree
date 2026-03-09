"""Additional tests for mapfree.core.state - coverage for untested paths."""

from mapfree.core.state import (
    PipelineState,
    load_state,
    save_state,
    mark_step_done,
    is_step_done,
    get_chunk_state,
    is_chunk_step_done,
    is_chunk_mapping_done,
    mark_chunk_step_done,
    reset_state,
    STATE_FILE,
    DEFAULT_STATE,
)


class TestPipelineState:
    def test_enum_values(self):
        assert PipelineState.IDLE.value == "idle"
        assert PipelineState.RUNNING.value == "running"
        assert PipelineState.FINISHED.value == "finished"
        assert PipelineState.ERROR.value == "error"


class TestLoadSaveState:
    def test_load_default_when_no_file(self, tmp_path):
        state = load_state(tmp_path)
        assert isinstance(state, dict)
        assert "chunks" in state

    def test_save_and_load_roundtrip(self, tmp_path):
        data = dict(DEFAULT_STATE)
        data["chunks"] = {}
        save_state(tmp_path, data)
        loaded = load_state(tmp_path)
        assert loaded == data

    def test_load_handles_corrupted_file(self, tmp_path):
        (tmp_path / STATE_FILE).write_text("NOT VALID JSON")
        state = load_state(tmp_path)
        assert isinstance(state, dict)

    def test_load_adds_missing_keys(self, tmp_path):
        # Save minimal state missing some keys
        (tmp_path / STATE_FILE).write_text('{"chunks": {}}')
        state = load_state(tmp_path)
        for key in DEFAULT_STATE:
            assert key in state


class TestMarkAndCheck:
    def test_mark_step_done(self, tmp_path):
        from mapfree.core.config import PIPELINE_STEPS
        step = PIPELINE_STEPS[0]
        mark_step_done(tmp_path, step)
        assert is_step_done(tmp_path, step) is True

    def test_is_step_done_false_initially(self, tmp_path):
        from mapfree.core.config import PIPELINE_STEPS
        step = PIPELINE_STEPS[0]
        assert is_step_done(tmp_path, step) is False

    def test_mark_chunk_step_done(self, tmp_path):
        from mapfree.core.config import CHUNK_STEPS
        step = CHUNK_STEPS[0]
        mark_chunk_step_done(tmp_path, "chunk_01", step)
        assert is_chunk_step_done(tmp_path, "chunk_01", step) is True

    def test_is_chunk_step_done_false_initially(self, tmp_path):
        from mapfree.core.config import CHUNK_STEPS
        step = CHUNK_STEPS[0]
        assert is_chunk_step_done(tmp_path, "chunk_01", step) is False

    def test_mark_chunk_invalid_step_no_op(self, tmp_path):
        mark_chunk_step_done(tmp_path, "chunk_01", "invalid_step")
        # Should not store invalid step
        state = get_chunk_state(tmp_path, "chunk_01")
        assert "invalid_step" not in state

    def test_is_chunk_step_done_invalid_step(self, tmp_path):
        result = is_chunk_step_done(tmp_path, "chunk_01", "invalid_step")
        assert result is False

    def test_is_chunk_mapping_done(self, tmp_path):
        assert is_chunk_mapping_done(tmp_path, "chunk_01") is False
        mark_chunk_step_done(tmp_path, "chunk_01", "mapping")
        assert is_chunk_mapping_done(tmp_path, "chunk_01") is True


class TestResetState:
    def test_reset_removes_file(self, tmp_path):
        save_state(tmp_path, dict(DEFAULT_STATE))
        assert (tmp_path / STATE_FILE).exists()
        reset_state(tmp_path)
        assert not (tmp_path / STATE_FILE).exists()

    def test_reset_nonexistent_no_error(self, tmp_path):
        reset_state(tmp_path)  # no file exists — should not raise


class TestLegacyMigration:
    def test_migrates_chunk_sparse_done(self, tmp_path):
        """Old 'chunk_sparse_done' list is migrated to 'chunks' dict."""
        legacy = {"chunks": {}, "chunk_sparse_done": ["chunk_01", "chunk_02"]}
        for step in DEFAULT_STATE:
            if step not in legacy:
                legacy[step] = False
        save_state(tmp_path, legacy)
        state = load_state(tmp_path)
        assert "chunk_01" in state["chunks"]
        assert "chunk_02" in state["chunks"]
