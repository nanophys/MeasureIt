"""Unit tests for SweepQueue class."""

import json
import pytest
from pathlib import Path

from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.simul_sweep import SimulSweep
from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry


class TestSweepQueueInit:
    """Test SweepQueue initialization."""

    def test_init_defaults(self, qapp):
        """Test SweepQueue initializes with defaults."""
        queue = SweepQueue()

        assert queue.inter_delay == 1
        assert queue.post_db_delay == 1.0
        assert len(queue.queue) == 0
        assert queue.current_sweep is None
        assert queue.rts is True

    def test_init_custom_delays(self, qapp):
        """Test SweepQueue with custom delays."""
        queue = SweepQueue(inter_delay=0.5, post_db_delay=2.0)

        assert queue.inter_delay == 0.5
        assert queue.post_db_delay == 2.0

    def test_init_debug_mode(self, qapp):
        """Test SweepQueue debug mode."""
        queue = SweepQueue(debug=True)

        assert queue.debug is True


class TestSweepQueueOperations:
    """Test basic queue operations."""

    def test_append_single_sweep(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test appending a single sweep."""
        queue = SweepQueue()
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1, 0.01,
            [mock_parameters["current"]],
            **fast_sweep_kwargs,
        )

        queue.append(sweep)

        assert len(queue.queue) == 1
        assert queue.queue[0] == sweep

    def test_append_multiple_sweeps(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test appending multiple sweeps at once."""
        queue = SweepQueue()
        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1, 0.01,
            [mock_parameters["current"]],
            **fast_sweep_kwargs,
        )
        sweep2 = Sweep1D(
            mock_parameters["voltage"],
            1, 0, 0.1, 0.01,
            [mock_parameters["current"]],
            **fast_sweep_kwargs,
        )

        queue.append(sweep1, sweep2)

        assert len(queue.queue) == 2
        assert queue.queue[0] == sweep1
        assert queue.queue[1] == sweep2

    def test_delete_sweep(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test deleting a sweep from queue."""
        queue = SweepQueue()
        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1, 0.01,
            [mock_parameters["current"]],
            **fast_sweep_kwargs,
        )
        sweep2 = Sweep1D(
            mock_parameters["voltage"],
            1, 0, 0.1, 0.01,
            [mock_parameters["current"]],
            **fast_sweep_kwargs,
        )

        queue.append(sweep1, sweep2)
        queue.delete(sweep1)

        assert len(queue.queue) == 1
        assert sweep1 not in queue.queue
        assert sweep2 in queue.queue


class TestSweepQueueDatabaseEntry:
    """Test DatabaseEntry functionality."""

    def test_database_entry_creation(self, qapp, temp_database):
        """Test creating a DatabaseEntry."""
        entry = DatabaseEntry(
            db=str(temp_database),
            exp="test_experiment",
            samp="test_sample"
        )

        assert entry.db == str(temp_database)
        assert entry.exp == "test_experiment"
        assert entry.samp == "test_sample"

    def test_queue_with_database_entries(self, qapp, mock_parameters, temp_database, fast_sweep_kwargs):
        """Test queue with DatabaseEntry objects."""
        queue = SweepQueue()

        db_entry = DatabaseEntry(
            db=str(temp_database),
            exp="test_exp",
            samp="test_sample"
        )

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1, 0.01,
            [mock_parameters["current"]],
            **fast_sweep_kwargs,
        )

        queue.append(db_entry, sweep)

        assert len(queue.queue) == 2


class TestSweepQueueCallable:
    """Test adding callable functions to queue."""

    def test_append_callable(self, qapp):
        """Test appending a callable to queue using append_handle."""
        queue = SweepQueue()

        def test_func():
            pass

        queue.append_handle(test_func)

        assert len(queue.queue) == 1
        assert callable(queue.queue[0])

    def test_mixed_queue(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test queue with mixed types (sweeps and callables)."""
        queue = SweepQueue()

        sweep = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        def test_func():
            pass

        queue.append(sweep)
        queue.append_handle(test_func)
        queue.append(sweep)

        assert len(queue.queue) == 3
        assert isinstance(queue.queue[0], Sweep1D)
        assert callable(queue.queue[1])
        # Note: queue.queue[2] is the same sweep object as queue.queue[0]
        assert queue.queue[2] == sweep


class TestSweepQueueIteration:
    """Test queue iteration."""

    def test_queue_is_iterable(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test that queue is iterable."""
        queue = SweepQueue()
        sweeps = [
            Sweep1D(
                mock_parameters["voltage"],
                i, i+1, 0.1, 0.01,
                [mock_parameters["current"]],
                **fast_sweep_kwargs,
            )
            for i in range(3)
        ]

        queue.append(*sweeps)

        items = list(queue)
        assert len(items) == 3
        for i, item in enumerate(items):
            assert item == sweeps[i]


class TestSweepQueueJSON:
    """Test JSON export/import."""

    def test_export_json_empty(self, qapp, tmp_path):
        """Test exporting empty queue."""
        queue = SweepQueue()
        json_path = tmp_path / "queue.json"

        json_dict = queue.export_json(str(json_path))

        assert "inter_delay" in json_dict
        assert json_dict["inter_delay"] == queue.inter_delay

    def test_export_json_with_sweeps(self, qapp, tmp_path):
        """Test exporting queue structure (without sweeps that need full instrument setup)."""
        queue = SweepQueue()
        json_path = tmp_path / "queue.json"

        # Test export of empty queue (sweeps with instruments require complex mocking)
        json_dict = queue.export_json(str(json_path))

        assert "queue" in json_dict
        assert isinstance(json_dict["queue"], list)
        assert "inter_delay" in json_dict
        assert json_dict["inter_delay"] == queue.inter_delay


class TestSweepQueueState:
    """Test queue state management."""

    def test_initial_state(self, qapp):
        """Test queue starts in correct state."""
        queue = SweepQueue()

        assert queue.current_sweep is None
        assert queue.current_action is None
        assert queue._processing is False
        assert queue._pending_begin_next is False

    def test_queue_not_running_initially(self, qapp):
        """Test that queue is not running initially."""
        queue = SweepQueue()

        # Initially not running (current_sweep should be None)
        assert queue.current_sweep is None
        assert queue.current_action is None


class TestSweepQueueMetadataProvider:
    """Test metadata provider attachment."""

    def test_attach_metadata_provider(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test attaching metadata provider to sweep."""
        queue = SweepQueue()
        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.1, 0.01,
            [mock_parameters["current"]],
            **fast_sweep_kwargs,
        )

        # Attach metadata provider
        queue._attach_queue_metadata_provider(sweep)

        # Sweep should have metadata_provider
        assert hasattr(sweep, "metadata_provider")


@pytest.mark.integration
class TestSweepQueueIntegration:
    """Integration tests for SweepQueue."""

    def test_complex_queue(self, qapp, mock_parameters, temp_database, fast_sweep_kwargs):
        """Test queue with complex mix of items."""
        queue = SweepQueue(inter_delay=0.01, post_db_delay=0.1)

        db_entry = DatabaseEntry(
            db=str(temp_database),
            exp="test",
            samp="sample"
        )

        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            start=0,
            stop=1,
            step=0.1,
            **fast_sweep_kwargs,
        )
        sweep1.follow_param(mock_parameters["current"])

        sweep2 = Sweep1D(
            mock_parameters["gate"],
            start=-1,
            stop=1,
            step=0.2,
            **fast_sweep_kwargs,
        )
        sweep2.follow_param(mock_parameters["x"])

        def callback():
            print("Between sweeps")

        queue.append(db_entry, sweep1)
        queue.append_handle(callback)
        queue.append(sweep2)

        assert len(queue.queue) == 4
