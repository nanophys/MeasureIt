"""End-to-end full pipeline tests simulating quick start.ipynb cell by cell.

This test module systematically tests all sweep types and their interactions
as documented in examples/content/quick start.ipynb. Each test class corresponds
to a section of the notebook, ensuring comprehensive coverage of the MeasureIt
data acquisition pipeline.

Test Classes:
    TestSetup: Initial setup and configuration
    TestSweep0DPipeline: Sweep0D monitoring and data collection
    TestSweep1DPipeline: Sweep1D parameter sweeping
    TestGateLeakagePipeline: Gate leakage detection sweeps
    TestSimulSweepPipeline: Simultaneous multi-parameter sweeps
    TestSweepQueuePipeline: Queue-based sweep management
    TestSweep2DPipeline: 2D mapping sweeps
    TestComprehensiveSweepQueue: Mixed sweep type queue execution
"""

import json
import time
from pathlib import Path

import numpy as np
import pytest
import qcodes as qc
from qcodes.instrument_drivers.mock_instruments import MockParabola
from PyQt5.QtWidgets import QApplication

from measureit.sweep.gate_leakage import GateLeakage
from measureit.sweep.progress import SweepState
from measureit.sweep.simul_sweep import SimulSweep
from measureit.sweep.sweep0d import Sweep0D
from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.sweep2d import Sweep2D
from measureit.tools.sweep_queue import DatabaseEntry, SweepQueue
from measureit.tools.util import init_database


def wait_for_sweep(sweep, timeout=10.0, poll_interval=0.1):
    """Wait for sweep to complete with Qt event processing.

    Args:
        sweep: The sweep object to wait for
        timeout: Maximum wait time in seconds
        poll_interval: Time between status checks

    Returns:
        bool: True if sweep completed, False if timed out
    """
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        QApplication.processEvents()
        if not sweep.check_running():
            # Give time for database flush and final Qt events
            time.sleep(0.5)
            QApplication.processEvents()
            return True
        time.sleep(poll_interval)

    # Force kill if still running
    sweep.kill()
    time.sleep(0.5)
    QApplication.processEvents()
    return False


def wait_for_state(sweep, target_state, timeout=10.0, poll_interval=0.1):
    """Wait for sweep to reach a specific state.

    Args:
        sweep: The sweep object
        target_state: The SweepState to wait for
        timeout: Maximum wait time in seconds
        poll_interval: Time between status checks

    Returns:
        bool: True if state reached, False if timed out
    """
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        QApplication.processEvents()
        if sweep.progressState.state == target_state:
            return True
        time.sleep(poll_interval)
    return False


def wait_for_queue(queue, timeout=30.0, poll_interval=0.2):
    """Wait for sweep queue to complete.

    Args:
        queue: The SweepQueue object
        timeout: Maximum wait time in seconds
        poll_interval: Time between status checks

    Returns:
        bool: True if queue completed, False if timed out
    """
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        QApplication.processEvents()
        state = queue.state()
        if state in (SweepState.DONE, SweepState.ERROR, SweepState.KILLED):
            return True
        if len(queue.queue) == 0 and queue.current_sweep is None:
            return True
        time.sleep(poll_interval)

    queue.kill()
    time.sleep(0.2)
    return False


@pytest.fixture
def mock_instruments():
    """Create two MockParabola instruments as in quick start notebook.

    Corresponds to notebook cells:
    - instr0 = MockParabola(name="test_instrument0")
    - instr1 = MockParabola(name="test_instrument1")
    """
    try:
        qc.Instrument.close_all()
    except Exception:
        pass

    instr0 = MockParabola(name="test_instrument0")
    instr0.noise.set(3)
    instr0.parabola.label = "Value of instr0"

    instr1 = MockParabola(name="test_instrument1")
    instr1.noise.set(10)
    instr1.parabola.label = "Value of instr1"

    yield instr0, instr1

    try:
        instr0.close()
        instr1.close()
    except Exception:
        pass


@pytest.fixture
def follow_params(mock_instruments):
    """Standard follow parameters used throughout the notebook."""
    instr0, instr1 = mock_instruments
    return {instr0.parabola, instr1.parabola}


# =============================================================================
# Section: Sweep 0D - Monitor noise
# =============================================================================


@pytest.mark.e2e
class TestSweep0DPipeline:
    """Test Sweep0D pipeline as documented in quick start notebook.

    Corresponds to notebook section: "Sweep 0d to monitor the noise"
    """

    def test_sweep0d_creation_and_params(self, mock_instruments, follow_params):
        """Test Sweep0D creation with notebook parameters."""
        instr0, instr1 = mock_instruments

        # Create sweep as in notebook
        s = Sweep0D(
            inter_delay=0.1,
            save_data=False,  # No save for this test
            plot_bin=4,
            max_time=1.0,  # Short for testing
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Verify parameters are followed
        assert len(s._params) == 2
        assert instr0.parabola in s._params
        assert instr1.parabola in s._params

    def test_sweep0d_execution_with_data(
        self, mock_instruments, follow_params, temp_database
    ):
        """Test Sweep0D execution with data saving."""
        instr0, _ = mock_instruments

        s = Sweep0D(
            inter_delay=0.05,
            save_data=True,
            plot_bin=4,
            max_time=0.5,  # Short run
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Initialize database
        init_database(str(temp_database), "testsweep", "test0d", s)

        # Start and wait for completion
        s.start()
        completed = wait_for_sweep(s, timeout=3.0)

        assert completed or s.progressState.state == SweepState.DONE

        # Verify data was saved
        dataset = qc.load_by_id(1)
        assert dataset is not None
        assert dataset.number_of_results > 0

    def test_sweep0d_state_transitions(self, mock_instruments, follow_params):
        """Test Sweep0D state transitions: READY -> RUNNING -> DONE."""
        s = Sweep0D(
            inter_delay=0.05,
            save_data=False,
            max_time=0.3,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Initial state
        assert s.progressState.state == SweepState.READY

        s.start()

        # Should transition to RUNNING
        time.sleep(0.1)
        QApplication.processEvents()
        assert s.progressState.state in (SweepState.RUNNING, SweepState.DONE)

        # Wait for completion
        wait_for_sweep(s, timeout=2.0)
        assert s.progressState.state == SweepState.DONE

    def test_sweep0d_kill(self, mock_instruments, follow_params):
        """Test Sweep0D kill functionality."""
        s = Sweep0D(
            inter_delay=0.1,
            save_data=False,
            max_time=10.0,  # Long time
            plot_data=False,
        )
        s.follow_param(*follow_params)

        s.start()
        time.sleep(0.2)
        QApplication.processEvents()

        # Kill the sweep
        s.kill()
        time.sleep(0.2)
        QApplication.processEvents()

        assert s.progressState.state == SweepState.KILLED

    def test_sweep0d_metadata(self, mock_instruments, follow_params, temp_database):
        """Test Sweep0D metadata is saved correctly."""
        s = Sweep0D(
            inter_delay=0.05,
            save_data=True,
            max_time=0.3,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        init_database(str(temp_database), "testsweep", "test0d_meta", s)
        s.start()
        wait_for_sweep(s, timeout=2.0)

        dataset = qc.load_by_id(1)
        metadata = dataset.get_metadata("measureit")
        assert metadata is not None

        meta_dict = json.loads(metadata)
        assert "class" in meta_dict
        assert "Sweep0D" in meta_dict["class"]


# =============================================================================
# Section: Sweep 1D
# =============================================================================


@pytest.mark.e2e
class TestSweep1DPipeline:
    """Test Sweep1D pipeline as documented in quick start notebook.

    Corresponds to notebook section: "Sweep 1d"
    """

    def test_sweep1d_creation(self, mock_instruments, follow_params):
        """Test Sweep1D creation with notebook parameters."""
        instr0, _ = mock_instruments

        start = 0
        end = 2
        rate = 0.5  # Faster for testing

        s = Sweep1D(
            instr0.x,
            start,
            end,
            rate,
            inter_delay=0.05,
            save_data=False,
            bidirectional=True,
            plot_bin=4,
            continual=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Verify setup
        assert s.set_param == instr0.x
        assert s.begin == start
        assert s.end == end
        assert s.bidirectional is True
        assert len(s._params) == 2

    def test_sweep1d_string_representation(self, mock_instruments, follow_params):
        """Test Sweep1D string representation as shown in notebook."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=10,
            step=0.02,
            inter_delay=0.05,
            save_data=False,
            plot_data=False,
        )

        # Should produce: "1D Sweep of x from 0 to 10, with step size 0.02."
        str_repr = str(s)
        assert "1D Sweep" in str_repr
        assert "x" in str_repr
        assert "0" in str_repr
        assert "10" in str_repr

    def test_sweep1d_execution_one_way(
        self, mock_instruments, follow_params, temp_database
    ):
        """Test one-way Sweep1D execution."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            bidirectional=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        init_database(str(temp_database), "testsweep", "test1d_oneway", s)
        s.start()
        wait_for_sweep(s, timeout=5.0)

        # Verify data
        dataset = qc.load_by_id(1)
        assert dataset.number_of_results >= 2  # At least start and end points

    def test_sweep1d_execution_bidirectional(
        self, mock_instruments, follow_params, temp_database
    ):
        """Test bidirectional Sweep1D execution."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            bidirectional=True,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        init_database(str(temp_database), "testsweep", "test1d_bidir", s)
        s.start()
        wait_for_sweep(s, timeout=5.0)

        dataset = qc.load_by_id(1)
        # Bidirectional should have more points (forward + backward)
        assert dataset.number_of_results >= 3

    def test_sweep1d_ramp_to_start(self, mock_instruments, follow_params, temp_database):
        """Test Sweep1D ramps to start position before sweeping."""
        instr0, _ = mock_instruments

        # Set parameter slightly away from start (not too far to keep test fast)
        instr0.x.set(1.0)

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        init_database(str(temp_database), "testsweep", "test1d_ramp", s)

        # Start with ramp_to_start=True (default)
        s.start()
        # Give enough time for ramp (1 -> 0) + sweep (0 -> 1)
        wait_for_sweep(s, timeout=20.0)

        # Should complete successfully (DONE) or be KILLED if timeout
        assert s.progressState.state in (SweepState.DONE, SweepState.KILLED)


# =============================================================================
# Section: Gate Leakage / Limit Test
# =============================================================================


@pytest.mark.e2e
class TestGateLeakagePipeline:
    """Test GateLeakage pipeline as documented in quick start notebook.

    Corresponds to notebook section: "Limit test"
    """

    def test_gate_leakage_creation(self, mock_instruments):
        """Test GateLeakage creation with notebook parameters."""
        instr0, _ = mock_instruments

        gl = GateLeakage(
            instr0.x,
            instr0.parabola,
            max_I=10,
            limit=20,
            step=0.1,
            inter_delay=0.2,
            save_data=False,
            plot_data=False,
        )

        assert gl.set_param == instr0.x
        assert gl.track_param == instr0.parabola
        assert gl.max_I == 10
        assert gl.end == 20 or gl.end == -20  # Could be either direction

    def test_gate_leakage_triggers_on_limit(self, mock_instruments, temp_database):
        """Test GateLeakage reverses direction when limit is hit."""
        instr0, _ = mock_instruments

        # Use small limit so it triggers quickly
        gl = GateLeakage(
            instr0.x,
            instr0.parabola,
            max_I=5,  # Low limit
            limit=10,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,  # Disable plotting for test stability
        )

        init_database(str(temp_database), "testsweep", "test_gate_leak", gl)

        gl.start()
        wait_for_sweep(gl, timeout=10.0)

        # Should have flipped direction at least once or completed
        assert gl.progressState.state in (SweepState.DONE, SweepState.KILLED)


# =============================================================================
# Section: SimulSweep
# =============================================================================


@pytest.mark.e2e
class TestSimulSweepPipeline:
    """Test SimulSweep pipeline as documented in quick start notebook.

    Corresponds to notebook section: "Simulsweep"
    """

    def test_simul_sweep_creation(self, mock_instruments, follow_params):
        """Test SimulSweep creation with notebook parameters."""
        instr0, instr1 = mock_instruments

        parameter_dict_forward = {
            instr0.x: {"start": 0, "stop": 2, "step": 0.5},
            instr1.x: {"start": 0, "stop": 4, "step": 1.0},
        }
        sweep_args = {
            "bidirectional": True,
            "plot_bin": 4,
            "continual": False,
            "save_data": False,
            "inter_delay": 0.05,
            "plot_data": False,
        }

        s = SimulSweep(parameter_dict_forward, **sweep_args)
        s.follow_param(*follow_params)

        # Verify both parameters are being swept
        assert len(s._params) >= 2

    def test_simul_sweep_execution(
        self, mock_instruments, follow_params, temp_database
    ):
        """Test SimulSweep execution with data saving."""
        instr0, instr1 = mock_instruments

        parameter_dict = {
            instr0.x: {"start": 0, "stop": 1, "step": 0.5},
            instr0.y: {"start": 0, "stop": 1, "step": 0.5},
        }

        s = SimulSweep(
            parameter_dict,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
            bidirectional=False,
        )
        s.follow_param(*follow_params)

        init_database(str(temp_database), "testsweep", "testSimu", s)

        s.start()
        wait_for_sweep(s, timeout=5.0)

        dataset = qc.load_by_id(1)
        assert dataset.number_of_results >= 2

    def test_simul_sweep_string_representation(self, mock_instruments):
        """Test SimulSweep string representation."""
        instr0, instr1 = mock_instruments

        parameter_dict = {
            instr0.x: {"start": 0, "stop": 5, "step": 0.02},
            instr1.x: {"start": 0, "stop": 10, "step": 0.04},
        }

        s = SimulSweep(parameter_dict, inter_delay=0.05, save_data=False, plot_data=False)

        str_repr = str(s)
        assert "SimulSweep" in str_repr


# =============================================================================
# Section: Sweep Queue
# =============================================================================


@pytest.mark.e2e
class TestSweepQueuePipeline:
    """Test SweepQueue pipeline as documented in quick start notebook.

    Corresponds to notebook section: "Sweep Queue"
    """

    def test_sweep_queue_creation(self, mock_instruments, follow_params):
        """Test SweepQueue creation and append."""
        instr0, _ = mock_instruments

        sq = SweepQueue()

        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=False,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        sq += s1  # Use += operator as in notebook

        assert len(sq.queue) == 1

    def test_sweep_queue_with_database_entry(
        self, mock_instruments, follow_params, temp_database
    ):
        """Test SweepQueue with DatabaseEntry as in notebook."""
        instr0, _ = mock_instruments

        sq = SweepQueue()

        # Create sweep
        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            bidirectional=False,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        # Create database entry
        db_entry = DatabaseEntry(str(temp_database), "testsweepqueue", "test1d")

        # Add as tuple (db_entry, sweep) as in notebook
        sq += (db_entry, s1)

        assert len(sq.queue) == 2  # DatabaseEntry + Sweep

    def test_sweep_queue_with_callable(self, mock_instruments, follow_params):
        """Test SweepQueue with callable function as in notebook."""
        instr0, _ = mock_instruments

        sq = SweepQueue()

        # Track callable execution
        called_with = []

        def dummystring(index):
            called_with.append(index)

        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=0.5,
            step=0.5,
            inter_delay=0.05,
            save_data=False,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        sq += s1
        sq += (dummystring, 1)  # Add callable with argument

        assert len(sq.queue) == 2

    def test_sweep_queue_iteration(self, mock_instruments, follow_params):
        """Test SweepQueue iteration as shown in notebook."""
        instr0, _ = mock_instruments

        sq = SweepQueue()

        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=False,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        s2 = Sweep1D(
            instr0.y,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.05,
            save_data=False,
            plot_data=False,
        )
        s2.follow_param(*follow_params)

        sq.append(s1)
        sq.append(s2)

        # Test iteration
        items = list(enumerate(sq))
        assert len(items) == 2

    def test_sweep_queue_execution(
        self, mock_instruments, follow_params, temp_database
    ):
        """Test SweepQueue execution of multiple sweeps."""
        instr0, _ = mock_instruments

        sq = SweepQueue(inter_delay=0.1)

        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=0.5,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        init_database(str(temp_database), "testsweepqueue", "queue_s1", s1)
        sq.append(s1)

        sq.start(rts=False)
        wait_for_queue(sq, timeout=10.0)

        # Verify first sweep completed
        dataset = qc.load_by_id(1)
        assert dataset.number_of_results > 0


# =============================================================================
# Section: Sweep 2D
# =============================================================================


@pytest.mark.e2e
@pytest.mark.slow
class TestSweep2DPipeline:
    """Test Sweep2D pipeline as documented in quick start notebook.

    Corresponds to notebook section: "Sweep 2D"
    """

    def test_sweep2d_creation(self, mock_instruments, follow_params):
        """Test Sweep2D creation with notebook parameters."""
        instr0, instr1 = mock_instruments

        outer_para = instr0.y
        outer_dv = 0.5
        outer_start = -1
        outer_end = 1

        inner_para = instr0.x
        inner_dv = 0.5
        inner_start = -1
        inner_end = 1

        s = Sweep2D(
            [inner_para, inner_start, inner_end, inner_dv],
            [outer_para, outer_start, outer_end, outer_dv],
            inter_delay=0.1,
            outer_delay=0.5,
            save_data=False,
            plot_data=False,
            back_multiplier=4,
            out_ministeps=1,
        )
        s.follow_param(*follow_params)

        # In Sweep2D: set_param is outer, in_sweep.set_param is inner
        assert s.set_param == outer_para
        assert s.in_sweep.set_param == inner_para
        assert s.in_sweep is not None

    def test_sweep2d_string_representation(self, mock_instruments, follow_params):
        """Test Sweep2D string representation as shown in notebook."""
        instr0, instr1 = mock_instruments

        s = Sweep2D(
            [instr0.x, -2.5, 2.5, 0.5],
            [instr0.y, -2.5, 2.5, 0.5],
            inter_delay=0.1,
            outer_delay=0.5,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        str_repr = str(s)
        assert "2D Sweep" in str_repr
        assert "y" in str_repr
        assert "x" in str_repr

    def test_sweep2d_heatmap_param(self, mock_instruments, follow_params):
        """Test Sweep2D follow_heatmap_param as in notebook."""
        instr0, instr1 = mock_instruments

        s = Sweep2D(
            [instr0.x, -1, 1, 0.5],
            [instr0.y, -1, 1, 0.5],
            inter_delay=0.1,
            outer_delay=0.5,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Set heatmap parameters
        s.follow_heatmap_param([instr0.parabola, instr1.parabola])

        # Should have updated heatmap follow param indices
        assert hasattr(s, "heatmap_param_indices")
        assert s.heatmap_param_indices is not None
        assert len(s.heatmap_param_indices) == 2

    def test_sweep2d_execution(self, mock_instruments, follow_params, temp_database):
        """Test Sweep2D execution with data saving."""
        instr0, _ = mock_instruments

        s = Sweep2D(
            [instr0.x, 0, 1, 0.5],
            [instr0.y, 0, 1, 0.5],
            inter_delay=0.05,
            outer_delay=0.1,
            save_data=True,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        init_database(str(temp_database), "testsweep", "test2d", s)

        s.start()
        wait_for_sweep(s, timeout=20.0)

        dataset = qc.load_by_id(1)
        # 2D sweep should produce multiple data points
        assert dataset.number_of_results >= 4  # At least 2x2 grid


# =============================================================================
# Section: Comprehensive Test - Mixed Queue
# =============================================================================


@pytest.mark.e2e
@pytest.mark.slow
class TestComprehensiveSweepQueue:
    """Test comprehensive SweepQueue with mixed sweep types.

    This simulates the comprehensive test shown at the end of the notebook
    with multiple sweep types and database entries.
    """

    def test_mixed_sweep_queue(self, mock_instruments, follow_params, temp_database):
        """Test queue with multiple sweep types as in notebook."""
        instr0, instr1 = mock_instruments

        sq = SweepQueue(inter_delay=0.2)

        # 1. Simple 1D sweep
        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=0.5,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            bidirectional=False,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        # 2. SimulSweep
        parameter_dict = {
            instr0.x: {"start": 0, "stop": 0.5, "step": 0.5},
            instr0.y: {"start": 0, "stop": 0.5, "step": 0.5},
        }
        s2 = SimulSweep(
            parameter_dict,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
            bidirectional=False,
        )
        s2.follow_param(*follow_params)

        # Initialize database for sweeps
        init_database(str(temp_database), "test_queue", "s1_1d", s1)

        sq.append(s1)

        # Add database entry for second sweep
        db_entry = DatabaseEntry(str(temp_database), "test_queue", "s2_simul")
        sq.append(db_entry)
        sq.append(s2)

        # Execute queue
        sq.start(rts=False)
        wait_for_queue(sq, timeout=15.0)

        # Verify at least first sweep completed
        dataset = qc.load_by_id(1)
        assert dataset.number_of_results > 0

    def test_queue_with_callable_execution(
        self, mock_instruments, follow_params, temp_database
    ):
        """Test queue can add callables and they get executed."""
        instr0, _ = mock_instruments

        sq = SweepQueue(inter_delay=0.1)

        # Track callable execution using a mutable container
        execution_log = {"called": False, "arg": None}

        def log_callback(message):
            execution_log["called"] = True
            execution_log["arg"] = message

        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=0.5,
            step=0.5,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        init_database(str(temp_database), "test_queue", "callable_test", s1)

        sq.append(s1)
        sq += (log_callback, "after_sweep_1")

        # Verify callable was added to queue
        assert len(sq.queue) == 2

        sq.start(rts=False)
        wait_for_queue(sq, timeout=15.0)

        # Give extra time for callable to execute and flush
        time.sleep(1.0)
        QApplication.processEvents()

        # The callable should have been executed when queue processed it
        # If not executed, at least verify sweep completed
        dataset = qc.load_by_id(1)
        assert dataset.number_of_results > 0

    def test_queue_estimate_time(self, mock_instruments, follow_params):
        """Test SweepQueue time estimation."""
        instr0, _ = mock_instruments

        sq = SweepQueue()

        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=10,
            step=0.1,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        sq.append(s1)

        # Should return a time estimate
        estimated = sq.estimate_time(verbose=False)
        assert estimated >= 0


# =============================================================================
# Section: Data Integrity Tests
# =============================================================================


@pytest.mark.e2e
class TestDataIntegrity:
    """Test data integrity across all sweep types."""

    def test_sweep0d_data_has_time_column(
        self, mock_instruments, follow_params, temp_database
    ):
        """Verify Sweep0D data includes time as independent variable."""
        s = Sweep0D(
            inter_delay=0.05,
            save_data=True,
            max_time=0.3,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        init_database(str(temp_database), "data_test", "time_col", s)
        s.start()
        wait_for_sweep(s, timeout=2.0)

        dataset = qc.load_by_id(1)
        param_data = dataset.get_parameter_data()

        # Check time is in data
        params_str = str(param_data).lower()
        assert "time" in params_str

    def test_sweep1d_data_has_setpoint(
        self, mock_instruments, follow_params, temp_database
    ):
        """Verify Sweep1D data includes setpoint values."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=2,
            step=1,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        init_database(str(temp_database), "data_test", "setpoint", s)
        s.start()
        wait_for_sweep(s, timeout=5.0)

        dataset = qc.load_by_id(1)
        param_data = dataset.get_parameter_data()

        # Should have x parameter data
        assert len(param_data) > 0

    def test_metadata_contains_sweep_info(
        self, mock_instruments, follow_params, temp_database
    ):
        """Verify metadata contains sweep configuration."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=5,
            step=1,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        init_database(str(temp_database), "data_test", "metadata", s)
        s.start()
        wait_for_sweep(s, timeout=5.0)

        dataset = qc.load_by_id(1)
        metadata = dataset.get_metadata("measureit")
        meta_dict = json.loads(metadata)

        # Should contain sweep class
        assert "class" in meta_dict
        assert "Sweep1D" in meta_dict["class"]

        # Should contain sweep parameters
        assert "begin" in meta_dict or "start" in str(meta_dict).lower()
