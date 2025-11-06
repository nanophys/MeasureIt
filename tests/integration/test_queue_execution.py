"""Integration tests for SweepQueue execution."""

import pytest
import time
from unittest.mock import Mock, patch

from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry
from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.progress import SweepState


@pytest.mark.integration
class TestQueueExecution:
    """Test queue execution flow."""

    def test_empty_queue_operations(self, qapp):
        """Test operations on empty queue."""
        queue = SweepQueue(inter_delay=0.01)

        assert len(queue.queue) == 0
        assert queue.current_sweep is None
        assert queue.current_action is None

    def test_queue_iteration(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test iterating over queue."""
        queue = SweepQueue()

        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.5,
            **fast_sweep_kwargs,
        )
        sweep2 = Sweep1D(
            mock_parameters["gate"],
            -1, 1, 0.5,
            **fast_sweep_kwargs,
        )

        queue.append(sweep1, sweep2)

        items = list(queue)
        assert len(items) == 2
        assert items[0] == sweep1
        assert items[1] == sweep2

    def test_queue_with_callable(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test queue with callable function."""
        queue = SweepQueue(inter_delay=0.01)

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.5,
            **fast_sweep_kwargs,
        )

        callback_called = []

        def callback():
            callback_called.append(True)

        queue.append(sweep)
        queue.append_handle(callback)

        assert len(queue.queue) == 2
        assert callable(queue.queue[1])

    def test_database_entry_in_queue(self, qapp, temp_database, mock_parameters, fast_sweep_kwargs):
        """Test DatabaseEntry in queue."""
        queue = SweepQueue(inter_delay=0.01)

        db_entry = DatabaseEntry(
            db=str(temp_database),
            exp="test_exp",
            samp="test_sample"
        )

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.5,
            **fast_sweep_kwargs,
        )

        queue.append(db_entry, sweep)

        assert len(queue.queue) == 2
        assert isinstance(queue.queue[0], DatabaseEntry)
        assert isinstance(queue.queue[1], Sweep1D)


@pytest.mark.integration
class TestQueueStateManagement:
    """Test queue state management during execution."""

    def test_queue_processing_flag(self, qapp):
        """Test _processing flag prevents concurrent execution."""
        queue = SweepQueue(inter_delay=0.01)

        assert queue._processing is False
        assert queue._pending_begin_next is False

    def test_metadata_provider_attachment(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test metadata provider is attached to sweeps."""
        queue = SweepQueue()

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.5,
            **fast_sweep_kwargs,
        )

        # Manually call the attachment method
        queue._attach_queue_metadata_provider(sweep)

        # Check that metadata_provider exists
        assert hasattr(sweep, "metadata_provider")


@pytest.mark.integration
class TestQueueModification:
    """Test modifying queue during execution."""

    def test_delete_from_queue(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test deleting sweeps from queue."""
        queue = SweepQueue()

        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.5,
            **fast_sweep_kwargs,
        )
        sweep2 = Sweep1D(
            mock_parameters["gate"],
            -1, 1, 0.5,
            **fast_sweep_kwargs,
        )

        queue.append(sweep1, sweep2)
        assert len(queue.queue) == 2

        queue.delete(sweep1)
        assert len(queue.queue) == 1
        assert sweep2 in queue.queue
        assert sweep1 not in queue.queue

    def test_replace_in_queue(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test replacing sweep in queue."""
        queue = SweepQueue()

        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.5,
            **fast_sweep_kwargs,
        )
        sweep2 = Sweep1D(
            mock_parameters["gate"],
            -1, 1, 0.5,
            **fast_sweep_kwargs,
        )

        queue.append(sweep1)
        queue.replace(0, sweep2)

        assert len(queue.queue) == 1
        assert queue.queue[0] == sweep2

    def test_move_in_queue(self, qapp, mock_parameters, fast_sweep_kwargs):
        """Test moving sweep in queue."""
        queue = SweepQueue()

        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 1, 0.5,
            **fast_sweep_kwargs,
        )
        sweep2 = Sweep1D(
            mock_parameters["gate"],
            -1, 1, 0.5,
            **fast_sweep_kwargs,
        )
        sweep3 = Sweep1D(
            mock_parameters["freq"],
            100, 1000, 100,
            **fast_sweep_kwargs,
        )

        queue.append(sweep1, sweep2, sweep3)

        # Move sweep1 forward by 1 position
        queue.move(sweep1, 1)

        # sweep2 should now be first
        assert queue.queue[0] == sweep2
        assert queue.queue[1] == sweep1


@pytest.mark.integration
class TestQueueDebugMode:
    """Test queue debug mode."""

    def test_debug_mode_initialization(self, qapp):
        """Test queue with debug mode."""
        queue = SweepQueue(debug=True)

        assert queue.debug is True

    def test_normal_mode(self, qapp):
        """Test queue without debug mode."""
        queue = SweepQueue(debug=False)

        assert queue.debug is False


@pytest.mark.integration
class TestQueueDelays:
    """Test queue delay configurations."""

    def test_custom_inter_delay(self, qapp):
        """Test custom inter_delay."""
        queue = SweepQueue(inter_delay=0.5)

        assert queue.inter_delay == 0.5

    def test_custom_post_db_delay(self, qapp):
        """Test custom post_db_delay."""
        queue = SweepQueue(post_db_delay=2.0)

        assert queue.post_db_delay == 2.0

    def test_both_delays(self, qapp):
        """Test setting both delays."""
        queue = SweepQueue(inter_delay=0.3, post_db_delay=1.5)

        assert queue.inter_delay == 0.3
        assert queue.post_db_delay == 1.5


@pytest.mark.integration
class TestComplexQueueScenarios:
    """Test complex queue scenarios."""

    def test_mixed_queue_with_all_types(self, qapp, temp_database, mock_parameters, fast_sweep_kwargs):
        """Test queue with sweeps, callables, and database entries."""
        queue = SweepQueue(inter_delay=0.01, post_db_delay=0.1)

        db_entry = DatabaseEntry(
            db=str(temp_database),
            exp="exp1",
            samp="sample1"
        )

        sweep1 = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )
        sweep1.follow_param(mock_parameters["current"])

        callback_count = []

        def callback():
            callback_count.append(1)

        sweep2 = Sweep1D(
            mock_parameters["gate"],
            -0.1, 0.1, 0.05,
            **fast_sweep_kwargs,
        )

        # Build complex queue
        queue.append(db_entry)
        queue.append(sweep1)
        queue.append_handle(callback)
        queue.append(sweep2)

        assert len(queue.queue) == 4

    def test_queue_with_multiple_db_switches(self, qapp, temp_database, mock_parameters, fast_sweep_kwargs):
        """Test queue switching between databases."""
        queue = SweepQueue(inter_delay=0.01)

        db_entry1 = DatabaseEntry(
            db=str(temp_database),
            exp="exp1",
            samp="sample1"
        )

        db_entry2 = DatabaseEntry(
            db=str(temp_database),
            exp="exp2",
            samp="sample2"
        )

        sweep = Sweep1D(
            mock_parameters["voltage"],
            0, 0.1, 0.05,
            **fast_sweep_kwargs,
        )

        queue.append(db_entry1, sweep, db_entry2, sweep)

        assert len(queue.queue) == 4
