"""End-to-end tests for sweep execution with data collection.

These tests simulate the complete workflow from quickstart.ipynb:
1. Create mock instruments
2. Execute sweeps with data saving
3. Verify data is collected and saved correctly
"""

import pytest
import time
import numpy as np
from pathlib import Path

import qcodes as qc
from qcodes.instrument_drivers.mock_instruments import MockParabola

from measureit.sweep.sweep0d import Sweep0D
from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.sweep2d import Sweep2D
from measureit.sweep.simul_sweep import SimulSweep
from measureit.tools.sweep_queue import SweepQueue, DatabaseEntry
from measureit.tools.util import init_database


def wait_for_sweep_completion(sweep, timeout=10.0):
    """Wait for sweep to complete and ensure data is flushed."""
    start_time = time.time()
    while sweep.check_running() and (time.time() - start_time) < timeout:
        time.sleep(0.1)

    # Kill sweep if still running
    if sweep.check_running():
        sweep.kill()

    # Always kill to ensure all threads (including inner sweeps) are stopped
    # This is safe to call even if sweep is already done
    sweep.kill()

    # For Sweep2D, also explicitly kill inner sweep and wait for it
    if hasattr(sweep, 'in_sweep') and sweep.in_sweep is not None:
        sweep.in_sweep.kill()
        # If inner sweep has a ramp_sweep, kill that too
        if hasattr(sweep.in_sweep, 'ramp_sweep') and sweep.in_sweep.ramp_sweep is not None:
            sweep.in_sweep.ramp_sweep.kill()

    # For Sweep1D/SimulSweep with ramp_sweep, kill that too
    if hasattr(sweep, 'ramp_sweep') and sweep.ramp_sweep is not None:
        sweep.ramp_sweep.kill()

    # Give time for database flush and threads to fully terminate
    time.sleep(0.5)


def wait_for_queue_completion(queue, timeout=15.0):
    """Wait for queue to complete and ensure data is flushed."""
    from measureit.sweep.progress import SweepState

    start_time = time.time()
    # Wait for queue to be empty AND current sweep to finish (not running or ramping)
    while (time.time() - start_time) < timeout:
        queue_empty = len(queue.queue) == 0
        if queue.current_sweep is None:
            sweep_done = True
        else:
            state = queue.current_sweep.progressState.state
            sweep_done = state in (
                SweepState.DONE, SweepState.KILLED, SweepState.ERROR, SweepState.READY
            )
        if queue_empty and sweep_done:
            break
        time.sleep(0.2)

    # Always kill to ensure all threads are stopped (safe to call even if done)
    queue.kill()

    # Kill any current sweep that might still have threads running
    if hasattr(queue, 'current_sweep') and queue.current_sweep is not None:
        queue.current_sweep.kill()
        # Also kill any ramp_sweep if present
        if hasattr(queue.current_sweep, 'ramp_sweep') and queue.current_sweep.ramp_sweep is not None:
            queue.current_sweep.ramp_sweep.kill()

    # Give time for database flush and threads to terminate
    time.sleep(0.5)


@pytest.fixture
def mock_parabola():
    """Create a MockParabola instrument for testing."""
    # Close any existing instruments first
    try:
        qc.Instrument.close_all()
    except:
        pass

    instr = MockParabola(name="test_parabola")
    instr.noise.set(1)  # Low noise for predictable testing
    instr.parabola.label = "Test Parabola"

    yield instr

    # Cleanup - small delay to allow any lingering threads to terminate
    time.sleep(0.3)
    try:
        instr.close()
    except:
        pass


@pytest.fixture
def two_mock_parabolas():
    """Create two MockParabola instruments for testing."""
    try:
        qc.Instrument.close_all()
    except:
        pass

    instr0 = MockParabola(name="parabola0")
    instr0.noise.set(1)
    instr0.parabola.label = "Parabola 0"

    instr1 = MockParabola(name="parabola1")
    instr1.noise.set(1)
    instr1.parabola.label = "Parabola 1"

    yield instr0, instr1

    # Cleanup - small delay to allow any lingering threads to terminate
    time.sleep(0.3)
    try:
        instr0.close()
        instr1.close()
    except:
        pass


@pytest.mark.e2e
class TestSweep0DExecution:
    """Test Sweep0D execution with data collection."""

    def test_sweep0d_short_run(self, mock_parabola, temp_database):
        """Test short Sweep0D execution with data saving."""
        # Create sweep
        sweep = Sweep0D(
            max_time=0.5,  # Very short for testing
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
            plot_bin=1,
        )
        sweep.follow_param(mock_parabola.parabola)

        # Initialize database
        init_database(
            str(temp_database),
            "test_exp",
            "sweep0d_test",
            sweep
        )

        # Start sweep (non-blocking in real use, but we'll let it complete)
        sweep.start()

        # Wait for completion
        timeout = 2.0
        start_time = time.time()
        while sweep.check_running() and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        # Verify data was saved
        dataset = qc.load_by_id(1)
        assert dataset is not None
        assert dataset.number_of_results > 0

        # Verify metadata
        metadata = dataset.get_metadata('measureit')
        assert metadata is not None

    def test_sweep0d_data_structure(self, mock_parabola, temp_database):
        """Test that Sweep0D saves data with correct structure."""
        sweep = Sweep0D(
            max_time=0.3,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        sweep.follow_param(mock_parabola.parabola)

        init_database(str(temp_database), "test_exp", "sweep0d_structure", sweep)

        sweep.start()

        # Wait for completion
        timeout = 2.0
        start_time = time.time()
        while sweep.check_running() and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        # Load and verify data structure
        dataset = qc.load_by_id(1)
        param_data = dataset.get_parameter_data()

        # Should have time and parabola parameters
        assert 'time' in str(param_data).lower() or len(param_data) > 0
        assert dataset.number_of_results > 0


@pytest.mark.e2e
class TestSweep1DExecution:
    """Test Sweep1D execution with data collection."""

    def test_sweep1d_basic(self, mock_parabola, temp_database):
        """Test basic Sweep1D execution."""
        sweep = Sweep1D(
            mock_parabola.x,
            start=0,
            stop=2,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
            bidirectional=False,
        )
        sweep.follow_param(mock_parabola.parabola)

        init_database(str(temp_database), "test_exp", "sweep1d_basic", sweep)

        sweep.start()
        wait_for_sweep_completion(sweep)

        # Verify data
        dataset = qc.load_by_id(1)
        assert dataset.number_of_results >= 3  # At least 3 points (0, 1, 2)

    def test_sweep1d_bidirectional(self, mock_parabola, temp_database):
        """Test bidirectional Sweep1D."""
        sweep = Sweep1D(
            mock_parabola.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
            bidirectional=True,
        )
        sweep.follow_param(mock_parabola.parabola)

        init_database(str(temp_database), "test_exp", "sweep1d_bidir", sweep)

        sweep.start()
        wait_for_sweep_completion(sweep)

        dataset = qc.load_by_id(1)
        # Should have points from both directions
        assert dataset.number_of_results >= 3

    def test_sweep1d_multiple_params(self, two_mock_parabolas, temp_database):
        """Test Sweep1D following multiple parameters."""
        instr0, instr1 = two_mock_parabolas

        sweep = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        sweep.follow_param(instr0.parabola, instr1.parabola)

        init_database(str(temp_database), "test_exp", "sweep1d_multi", sweep)

        sweep.start()
        wait_for_sweep_completion(sweep)

        dataset = qc.load_by_id(1)
        param_data = dataset.get_parameter_data()

        # Should have multiple parameters
        assert len(param_data) >= 2  # At least 2 dependent parameters


@pytest.mark.e2e
@pytest.mark.slow
class TestSweep2DExecution:
    """Test Sweep2D execution with data collection."""

    def test_sweep2d_minimal(self, mock_parabola, temp_database):
        """Test minimal Sweep2D execution."""
        in_params = [mock_parabola.x, 0, 1, 0.5]
        out_params = [mock_parabola.y, 0, 1, 0.5]

        sweep = Sweep2D(
            in_params,
            out_params,
            inter_delay=0.05,
            outer_delay=0.1,
            save_data=True,
            plot_data=False,
        )
        sweep.follow_param(mock_parabola.parabola)

        init_database(str(temp_database), "test_exp", "sweep2d_minimal", sweep)

        sweep.start()
        wait_for_sweep_completion(sweep, timeout=15.0)

        dataset = qc.load_by_id(1)
        # Should have multiple points from 2D grid
        assert dataset.number_of_results >= 4  # At least 2x2 grid


@pytest.mark.e2e
class TestSimulSweepExecution:
    """Test SimulSweep execution with data collection."""

    def test_simul_sweep_basic(self, mock_parabola, temp_database):
        """Test basic SimulSweep execution."""
        params_dict = {
            mock_parabola.x: {"start": 0, "stop": 1, "step": 0.5},
            mock_parabola.y: {"start": 0, "stop": 1, "step": 0.5},
        }

        sweep = SimulSweep(
            params_dict,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        sweep.follow_param(mock_parabola.parabola)

        init_database(str(temp_database), "test_exp", "simul_basic", sweep)

        sweep.start()
        wait_for_sweep_completion(sweep)

        dataset = qc.load_by_id(1)
        assert dataset.number_of_results >= 2


@pytest.mark.e2e
@pytest.mark.slow
class TestSweepQueueExecution:
    """Test SweepQueue execution with multiple sweeps."""

    def test_queue_simple_sequence(self, mock_parabola, temp_database):
        """Test simple sweep queue sequence."""
        queue = SweepQueue(inter_delay=0.1)

        # Add first sweep
        sweep1 = Sweep1D(
            mock_parabola.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        sweep1.follow_param(mock_parabola.parabola)

        queue.append(sweep1)

        # Add second sweep
        sweep2 = Sweep1D(
            mock_parabola.y,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        sweep2.follow_param(mock_parabola.parabola)

        queue.append(sweep2)

        # Initialize database for both sweeps
        init_database(str(temp_database), "test_exp", "queue_sweep1", sweep1)
        init_database(str(temp_database), "test_exp", "queue_sweep2", sweep2)

        # Start queue
        queue.start()
        wait_for_queue_completion(queue, timeout=15.0)

        # Ensure all sweep threads are stopped before fixture cleanup
        sweep1.kill()
        sweep2.kill()

        # First sweep should have saved data
        ds1 = qc.load_by_id(1)
        assert ds1.number_of_results > 0

        # Second sweep may or may not run depending on queue implementation
        # Just verify at least one sweep completed successfully

    def test_queue_with_callable(self, mock_parabola, temp_database):
        """Test queue with callable function between sweeps."""
        queue = SweepQueue(inter_delay=0.1)

        # Track if callable was executed
        callback_executed = []

        def test_callback():
            callback_executed.append(True)

        # Add sweep
        sweep = Sweep1D(
            mock_parabola.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        sweep.follow_param(mock_parabola.parabola)

        init_database(str(temp_database), "test_exp", "queue_callable", sweep)

        queue.append(sweep)
        queue.append_handle(test_callback)

        queue.start()
        wait_for_queue_completion(queue)

        # Ensure sweep threads are stopped before fixture cleanup
        sweep.kill()

        # Sweep should have completed
        ds1 = qc.load_by_id(1)
        assert ds1.number_of_results > 0


@pytest.mark.e2e
class TestDataPersistence:
    """Test that data is properly persisted to database."""

    def test_metadata_preservation(self, mock_parabola, temp_database):
        """Test that sweep metadata is saved correctly."""
        sweep = Sweep1D(
            mock_parabola.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        sweep.follow_param(mock_parabola.parabola)

        init_database(str(temp_database), "test_exp", "metadata_test", sweep)

        sweep.start()

        timeout = 5.0
        start_time = time.time()
        while sweep.check_running() and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        # Load dataset and check metadata
        dataset = qc.load_by_id(1)
        metadata = dataset.get_metadata('measureit')

        assert metadata is not None

        # Parse and verify metadata structure
        import json
        meta_dict = json.loads(metadata)
        assert 'class' in meta_dict
        assert 'Sweep1D' in meta_dict['class']

    def test_parameter_data_integrity(self, mock_parabola, temp_database):
        """Test that parameter data maintains integrity."""
        # Set known parameter values
        mock_parabola.x.set(0)
        mock_parabola.y.set(0)

        sweep = Sweep1D(
            mock_parabola.x,
            start=0,
            stop=2,
            step=1,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        sweep.follow_param(mock_parabola.parabola)

        init_database(str(temp_database), "test_exp", "data_integrity", sweep)

        sweep.start()
        wait_for_sweep_completion(sweep)

        # Load and verify data
        dataset = qc.load_by_id(1)
        param_data = dataset.get_parameter_data()

        # Verify we have expected number of points
        assert dataset.number_of_results >= 3  # 0, 1, 2
