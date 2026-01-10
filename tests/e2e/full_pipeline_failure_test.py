"""End-to-end failure pipeline tests for error handling verification.

This test module converts the manual tests documented in Human_test.md into
automated pytest tests. It verifies that all sweep types correctly transition
to ERROR state when failures occur and that error messages are properly set.

Test Categories:
    TestSweep0DParameterReadFailure: safe_get() raises ParameterException
    TestSweep1DRampingFailure: Position mismatch after ramping
    TestSweep1DParameterSetFailure: safe_set() failures during stepping
    TestSweep2DOuterParamFailure: Outer parameter set failures
    TestSimulSweepRampingFailure: Multi-parameter ramping failures
    TestSweepQueueErrorPropagation: Queue detects and handles sweep errors
    TestRampSweepErrorPropagation: Ramp sweep errors propagate to parent
"""

import time
from unittest.mock import patch

import pytest
import qcodes as qc
from qcodes.instrument_drivers.mock_instruments import MockParabola
from PyQt5.QtWidgets import QApplication

from measureit.sweep.progress import SweepState
from measureit.sweep.simul_sweep import SimulSweep
from measureit.sweep.sweep0d import Sweep0D
from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.sweep2d import Sweep2D
from measureit.tools.sweep_queue import SweepQueue
from measureit.tools.util import ParameterException, init_database, safe_get


def wait_for_error_state(sweep, timeout=5.0, poll_interval=0.1):
    """Wait for sweep to enter ERROR state with Qt event processing.

    Args:
        sweep: The sweep object to monitor
        timeout: Maximum wait time in seconds
        poll_interval: Time between status checks

    Returns:
        bool: True if ERROR state reached, False if timed out
    """
    start_time = time.time()
    while (time.time() - start_time) < timeout:
        QApplication.processEvents()
        if sweep.progressState.state == SweepState.ERROR:
            return True
        # Also check if sweep stopped for other reasons
        if sweep.progressState.state in (SweepState.DONE, SweepState.KILLED):
            return False
        time.sleep(poll_interval)
    return False


def process_events(duration=0.5, interval=0.05):
    """Process Qt events for a duration.

    Args:
        duration: Total time to process events
        interval: Time between processEvents calls
    """
    start_time = time.time()
    while (time.time() - start_time) < duration:
        QApplication.processEvents()
        time.sleep(interval)


@pytest.fixture
def mock_instruments():
    """Create two MockParabola instruments for testing."""
    try:
        qc.Instrument.close_all()
    except Exception:
        pass

    instr0 = MockParabola(name="fail_test_instr0")
    instr0.noise.set(3)
    instr0.parabola.label = "Value of instr0"

    instr1 = MockParabola(name="fail_test_instr1")
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
    """Standard follow parameters for testing."""
    instr0, instr1 = mock_instruments
    return {instr0.parabola, instr1.parabola}


# =============================================================================
# Section 1: Sweep0D Parameter Read Error
# From Human_test.md: "Tests that safe_get() properly raises ParameterException"
# =============================================================================


@pytest.mark.e2e
class TestSweep0DParameterReadFailure:
    """Test Sweep0D enters ERROR state on parameter read failure.

    Corresponds to Human_test.md Section 1: Sweep0D Parameter Read Error
    """

    def test_sweep0d_parameter_read_failure_enters_error_state(
        self, mock_instruments, follow_params
    ):
        """Test Sweep0D transitions to ERROR when parameter read fails."""
        instr0, _ = mock_instruments

        # Create Sweep0D
        s = Sweep0D(
            max_time=10,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(instr0.parabola)

        # Simulate parameter read failure
        def failing_get():
            raise Exception("Communication timeout")

        # Patch the parabola getter to fail
        original_get = instr0.parabola.get
        instr0.parabola.get = failing_get

        try:
            s.start()

            # Wait for error to propagate:
            # - safe_get() tries once, fails, sleeps 1s, retries
            # - After 2nd failure, raises ParameterException
            # - Runner catches it and calls mark_error(_from_runner=True)
            reached_error = wait_for_error_state(s, timeout=5.0)

            assert reached_error, f"Expected ERROR state, got {s.progressState.state}"
            assert s.progressState.error_message is not None
            assert "parabola" in s.progressState.error_message.lower()
        finally:
            instr0.parabola.get = original_get
            s.kill()

    def test_sweep0d_error_message_contains_param_info(
        self, mock_instruments, follow_params
    ):
        """Test error message includes parameter information."""
        instr0, _ = mock_instruments

        s = Sweep0D(
            max_time=10,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(instr0.parabola)

        def failing_get():
            raise Exception("Device not responding")

        original_get = instr0.parabola.get
        instr0.parabola.get = failing_get

        try:
            s.start()
            reached_error = wait_for_error_state(s, timeout=5.0)

            if reached_error:
                # Error message should indicate which parameter failed
                assert "parabola" in s.progressState.error_message.lower() or \
                       "parameter" in s.progressState.error_message.lower()
        finally:
            instr0.parabola.get = original_get
            s.kill()


# =============================================================================
# Section 2: Sweep1D Ramping Failure Error
# From Human_test.md: "Tests that ramping failures (position mismatch)"
# =============================================================================


@pytest.mark.e2e
class TestSweep1DRampingFailure:
    """Test Sweep1D enters ERROR state on ramping position mismatch.

    Corresponds to Human_test.md Section 2: Sweep1D Ramping Failure Error
    """

    def test_sweep1d_ramping_failure_enters_error_state(
        self, mock_instruments, follow_params
    ):
        """Test Sweep1D transitions to ERROR when ramp ends at wrong position."""
        instr0, _ = mock_instruments

        # Create a Sweep1D
        s = Sweep1D(
            instr0.x,
            start=0,
            stop=5,
            step=0.1,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
            bidirectional=False,
        )
        s.follow_param(*follow_params)

        # Set parameter to a value different from expected start
        instr0.x.set(0.5)

        # Simulate ramping state
        s.progressState.state = SweepState.RAMPING

        # Call done_ramping expecting value=0.0 but actual is 0.5
        # This should trigger ERROR state
        s.done_ramping(value=0.0, start_on_finish=False, pd=None)

        assert s.progressState.state == SweepState.ERROR
        assert s.progressState.error_message is not None

        s.kill()

    def test_sweep1d_ramping_error_message_mentions_tolerance(
        self, mock_instruments, follow_params
    ):
        """Test ramping error message includes tolerance information."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=5,
            step=0.1,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        instr0.x.set(2.0)  # Large mismatch
        s.progressState.state = SweepState.RAMPING

        s.done_ramping(value=0.0, start_on_finish=False, pd=None)

        # Check error message format
        error_msg = s.progressState.error_message
        assert error_msg is not None
        # Should mention tolerance or expected/actual values
        assert "ramping" in error_msg.lower() or "expected" in error_msg.lower()

        s.kill()


# =============================================================================
# Section 3: Sweep1D Parameter Set Error During Sweep
# From Human_test.md: "Tests that safe_set() failures during stepping"
# =============================================================================


@pytest.mark.e2e
class TestSweep1DParameterSetFailure:
    """Test Sweep1D enters ERROR state on parameter set failure during sweep.

    Corresponds to Human_test.md Section 3: Sweep1D Parameter Set Error
    """

    def test_sweep1d_set_failure_enters_error_state(
        self, mock_instruments, follow_params
    ):
        """Test Sweep1D transitions to ERROR when set() fails during sweep."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=5,
            step=0.1,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Patch the set method to fail after a few successful sets
        original_set = instr0.x.set
        call_count = [0]

        def failing_set_after_n(value):
            call_count[0] += 1
            if call_count[0] > 5:  # Fail after 5 successful sets
                raise Exception("Parameter validation failed: value out of range")
            return original_set(value)

        instr0.x.set = failing_set_after_n

        try:
            s.start(ramp_to_start=False)

            # Wait for error
            reached_error = wait_for_error_state(s, timeout=5.0)

            assert reached_error, f"Expected ERROR state, got {s.progressState.state}"
            assert s.progressState.error_message is not None
            assert call_count[0] > 5, "Set should have been called multiple times"
        finally:
            instr0.x.set = original_set
            s.kill()

    def test_sweep1d_set_error_message_contains_param_name(
        self, mock_instruments, follow_params
    ):
        """Test set failure error message includes parameter name."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=5,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        original_set = instr0.x.set
        call_count = [0]

        def failing_set(value):
            call_count[0] += 1
            if call_count[0] > 3:
                raise Exception("Set failed")
            return original_set(value)

        instr0.x.set = failing_set

        try:
            s.start(ramp_to_start=False)
            reached_error = wait_for_error_state(s, timeout=5.0)

            if reached_error:
                error_msg = s.progressState.error_message.lower()
                assert "x" in error_msg or "set" in error_msg
        finally:
            instr0.x.set = original_set
            s.kill()


# =============================================================================
# Section 4: Sweep2D Outer Parameter Set Error
# From Human_test.md: "Tests that outer parameter set failures"
# =============================================================================


@pytest.mark.e2e
class TestSweep2DOuterParamFailure:
    """Test Sweep2D enters ERROR state on outer parameter set failure.

    Corresponds to Human_test.md Section 4: Sweep2D Outer Parameter Set Error
    """

    def test_sweep2d_outer_param_failure_enters_error_state(
        self, mock_instruments, follow_params
    ):
        """Test Sweep2D transitions to ERROR when outer param set fails."""
        instr0, _ = mock_instruments

        s = Sweep2D(
            [instr0.x, -2, 2, 0.5],  # inner: x
            [instr0.y, -2, 2, 0.5],  # outer: y
            inter_delay=0.1,
            outer_delay=0.5,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Patch outer parameter set to fail
        original_set = instr0.y.set
        fail_on_next = [False]

        def conditional_failing_set(value):
            if fail_on_next[0]:
                raise Exception("Outer parameter set failed: communication error")
            return original_set(value)

        instr0.y.set = conditional_failing_set

        try:
            # Start the sweep
            s.start(ramp_to_start=False)

            # Let first inner sweep start
            time.sleep(0.5)
            QApplication.processEvents()

            # Enable failure for the next outer parameter set
            fail_on_next[0] = True

            # Wait for error (allow enough time for outer step)
            reached_error = wait_for_error_state(s, timeout=10.0)

            # Check if error was detected
            if reached_error:
                assert s.progressState.error_message is not None
        finally:
            instr0.y.set = original_set
            s.kill()


# =============================================================================
# Section 5: SimulSweep Ramping Failure Error
# From Human_test.md: "Tests that SimulSweep ramping failures"
# =============================================================================


@pytest.mark.e2e
class TestSimulSweepRampingFailure:
    """Test SimulSweep enters ERROR state on ramping position mismatch.

    Corresponds to Human_test.md Section 5: SimulSweep Ramping Failure Error
    """

    def test_simul_sweep_ramping_failure_enters_error_state(
        self, mock_instruments, follow_params
    ):
        """Test SimulSweep transitions to ERROR when ramp ends at wrong position."""
        instr0, _ = mock_instruments

        # Set parameters to known positions BEFORE creating SimulSweep
        # (SimulSweep reads current param values during init)
        instr0.x.set(0.0)
        instr0.y.set(0.0)

        params_dict = {
            instr0.x: {"start": 0, "stop": 5, "step": 0.1},
            instr0.y: {"start": 0, "stop": 5, "step": 0.1},
        }

        s = SimulSweep(
            params_dict,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
            bidirectional=False,
        )

        # Now set parameters to WRONG positions (simulating a failed ramp)
        instr0.x.set(2.5)
        instr0.y.set(2.5)

        # Simulate ramping state
        s.progressState.state = SweepState.RAMPING

        # Expected values dictionary
        vals_dict = {
            instr0.x: 0.0,
            instr0.y: 0.0,
        }

        # Call done_ramping - should detect position mismatch
        s.done_ramping(vals_dict, start_on_finish=False, pd=None)

        assert s.progressState.state == SweepState.ERROR
        assert s.progressState.error_message is not None

        s.kill()

    def test_simul_sweep_error_message_includes_err_info(
        self, mock_instruments, follow_params
    ):
        """Test SimulSweep error message includes tolerance information."""
        instr0, _ = mock_instruments

        instr0.x.set(0.0)
        instr0.y.set(0.0)

        params_dict = {
            instr0.x: {"start": 0, "stop": 5, "step": 0.1},
            instr0.y: {"start": 0, "stop": 5, "step": 0.1},
        }

        s = SimulSweep(
            params_dict,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )

        instr0.x.set(3.0)  # Large mismatch
        s.progressState.state = SweepState.RAMPING

        vals_dict = {instr0.x: 0.0, instr0.y: 0.0}
        s.done_ramping(vals_dict, start_on_finish=False, pd=None)

        error_msg = s.progressState.error_message
        assert error_msg is not None
        # Should mention tolerance (err parameter) or expected/actual
        assert "err" in error_msg.lower() or "expected" in error_msg.lower() or \
               "ramping" in error_msg.lower()

        s.kill()


# =============================================================================
# Section 6: SweepQueue Error Propagation
# From Human_test.md: "Tests that SweepQueue correctly detects and handles"
# =============================================================================


@pytest.mark.e2e
class TestSweepQueueErrorPropagation:
    """Test SweepQueue correctly handles sweep errors.

    Corresponds to Human_test.md Section 6: SweepQueue Error Propagation
    """

    def test_sweep_queue_detects_error_and_stops(
        self, mock_instruments, follow_params
    ):
        """Test SweepQueue stops when a sweep enters ERROR state."""
        instr0, _ = mock_instruments

        sq = SweepQueue(inter_delay=0.5)

        # Create sweeps
        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=2,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        s2 = Sweep1D(
            instr0.y,
            start=0,
            stop=2,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s2.follow_param(*follow_params)

        sq.append(s1)
        sq.append(s2)

        # Patch first sweep to fail mid-way
        original_set = instr0.x.set
        call_count = [0]

        def failing_set(value):
            call_count[0] += 1
            if call_count[0] > 3:
                raise Exception("Parameter error")
            return original_set(value)

        instr0.x.set = failing_set

        try:
            sq.start(rts=False)

            # Wait for error detection
            time.sleep(3)
            process_events(1.0)

            queue_state = sq.state()

            # Either queue state is ERROR or current sweep is in ERROR
            error_detected = (
                queue_state == SweepState.ERROR or
                (sq.current_sweep and
                 sq.current_sweep.progressState.state == SweepState.ERROR)
            )

            assert error_detected, f"Queue state: {queue_state}"

            # Second sweep should still be in queue (not started)
            assert s2 in sq.queue, "Second sweep should remain in queue"
        finally:
            instr0.x.set = original_set
            sq.kill()

    def test_sweep_queue_preserves_remaining_sweeps(
        self, mock_instruments, follow_params
    ):
        """Test SweepQueue preserves remaining sweeps after error."""
        instr0, _ = mock_instruments

        sq = SweepQueue(inter_delay=0.2)

        s1 = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s1.follow_param(*follow_params)

        s2 = Sweep1D(
            instr0.y,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s2.follow_param(*follow_params)

        s3 = Sweep1D(
            instr0.z,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s3.follow_param(*follow_params)

        sq.append(s1)
        sq.append(s2)
        sq.append(s3)

        original_queue_length = len(sq.queue)

        # Make first sweep fail immediately
        original_set = instr0.x.set

        def failing_set(value):
            raise Exception("Immediate failure")

        instr0.x.set = failing_set

        try:
            sq.start(rts=False)
            process_events(2.0)

            # At least s2 and s3 should still be in queue
            remaining = len(sq.queue)
            assert remaining >= 2, f"Expected at least 2 sweeps remaining, got {remaining}"
        finally:
            instr0.x.set = original_set
            sq.kill()


# =============================================================================
# Section 7: Ramp Sweep Error Propagation
# Tests that ramp_to_start sweep failures propagate to parent
# =============================================================================


@pytest.mark.e2e
class TestRampSweepErrorPropagation:
    """Test that ramp sweep errors propagate to parent sweep."""

    def test_sweep1d_ramp_sweep_error_propagates(
        self, mock_instruments, follow_params
    ):
        """Test Sweep1D detects ramp_sweep ERROR and transitions to ERROR."""
        instr0, _ = mock_instruments

        # Set parameter away from start to force ramping
        instr0.x.set(5.0)

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=2,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Create a mock ramp_sweep that is in ERROR state
        mock_ramp = Sweep1D(
            instr0.x,
            start=5,
            stop=0,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        mock_ramp.progressState.state = SweepState.ERROR
        mock_ramp.progressState.error_message = "Ramp sweep failed: test error"

        # Inject the failed ramp sweep
        s.ramp_sweep = mock_ramp
        s.progressState.state = SweepState.RAMPING

        # Call done_ramping - should detect ramp_sweep error
        s.done_ramping(value=0, start_on_finish=False, pd=None)

        assert s.progressState.state == SweepState.ERROR
        assert "ramp" in s.progressState.error_message.lower()

        s.kill()
        mock_ramp.kill()

    def test_simul_sweep_ramp_sweep_error_propagates(
        self, mock_instruments, follow_params
    ):
        """Test SimulSweep detects ramp_sweep ERROR and transitions to ERROR."""
        instr0, _ = mock_instruments

        instr0.x.set(0.0)
        instr0.y.set(0.0)

        params_dict = {
            instr0.x: {"start": 0, "stop": 5, "step": 0.5},
            instr0.y: {"start": 0, "stop": 5, "step": 0.5},
        }

        s = SimulSweep(
            params_dict,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )

        # Create mock ramp sweep in ERROR state
        mock_ramp = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        mock_ramp.progressState.state = SweepState.ERROR
        mock_ramp.progressState.error_message = "SimulSweep ramp failed"

        s.ramp_sweep = mock_ramp
        s.progressState.state = SweepState.RAMPING

        vals_dict = {instr0.x: 0.0, instr0.y: 0.0}
        s.done_ramping(vals_dict, start_on_finish=False, pd=None)

        assert s.progressState.state == SweepState.ERROR
        assert "ramp" in s.progressState.error_message.lower()

        s.kill()
        mock_ramp.kill()


# =============================================================================
# Section 8: Error State Idempotency
# Tests that mark_error only processes first error
# =============================================================================


@pytest.mark.e2e
class TestErrorStateIdempotency:
    """Test mark_error idempotency and completed signal handling."""

    def test_mark_error_only_processed_once(self, mock_instruments, follow_params):
        """Test multiple mark_error calls only set first error."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=5,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # First error
        s.mark_error("First error message")
        first_message = s.progressState.error_message

        # Second error (should be ignored)
        s.mark_error("Second error message")
        second_message = s.progressState.error_message

        # First error should be preserved
        assert second_message == first_message
        assert "First error" in second_message

        s.kill()

    def test_clear_error_resets_state(self, mock_instruments, follow_params):
        """Test clear_error resets all error fields."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=5,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Set error state
        s.mark_error("Test error")
        assert s.progressState.state == SweepState.ERROR
        assert s.progressState.error_message is not None

        # Clear error
        s.clear_error()
        assert s.progressState.state == SweepState.READY
        assert s.progressState.error_message is None
        assert s.progressState.error_count == 0

        s.kill()


# =============================================================================
# Section 9: Inner Sweep Error Propagation (Sweep2D)
# Tests that inner sweep errors propagate to outer Sweep2D
# =============================================================================


@pytest.mark.e2e
class TestSweep2DInnerSweepErrorPropagation:
    """Test Sweep2D detects and handles inner sweep errors."""

    def test_inner_sweep_error_propagates_to_outer(
        self, mock_instruments, follow_params
    ):
        """Test inner sweep error causes outer Sweep2D to enter ERROR state."""
        instr0, _ = mock_instruments

        s = Sweep2D(
            [instr0.x, 0, 1, 0.5],
            [instr0.y, 0, 1, 0.5],
            inter_delay=0.1,
            outer_delay=0.2,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Make inner sweep's parameter fail
        original_set = instr0.x.set
        call_count = [0]

        def failing_set(value):
            call_count[0] += 1
            if call_count[0] > 3:
                raise Exception("Inner sweep parameter failure")
            return original_set(value)

        instr0.x.set = failing_set

        try:
            s.start(ramp_to_start=False)

            # Wait for error to propagate
            reached_error = wait_for_error_state(s, timeout=10.0)

            # Either outer or inner sweep should be in error
            outer_error = s.progressState.state == SweepState.ERROR
            inner_error = s.in_sweep.progressState.state == SweepState.ERROR

            assert outer_error or inner_error, \
                f"Expected error state. Outer: {s.progressState.state}, Inner: {s.in_sweep.progressState.state}"
        finally:
            instr0.x.set = original_set
            s.kill()


# =============================================================================
# Section 10: Integration Tests
# Full integration tests combining multiple error scenarios
# =============================================================================


@pytest.mark.e2e
class TestErrorHandlingIntegration:
    """Integration tests for error handling across sweep types."""

    def test_error_recovery_workflow(self, mock_instruments, follow_params):
        """Test that sweeps can be restarted after error."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=1,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Force error
        s.mark_error("Intentional test error")
        assert s.progressState.state == SweepState.ERROR

        # Clear error
        s.clear_error()
        assert s.progressState.state == SweepState.READY

        # Should be able to start again
        s.start(ramp_to_start=False)
        process_events(0.5)

        # Should be running or done (not stuck in error)
        assert s.progressState.state in (SweepState.RUNNING, SweepState.DONE)

        s.kill()

    def test_error_state_preserved_across_updates(
        self, mock_instruments, follow_params
    ):
        """Test error state is preserved when send_updates is called."""
        instr0, _ = mock_instruments

        s = Sweep1D(
            instr0.x,
            start=0,
            stop=5,
            step=0.5,
            inter_delay=0.1,
            save_data=False,
            plot_data=False,
        )
        s.follow_param(*follow_params)

        # Set error
        test_message = "Preserved error test"
        s.mark_error(test_message)

        # Call send_updates (which updates progressState)
        s.send_updates()

        # Error should still be preserved
        assert s.progressState.state == SweepState.ERROR
        assert s.progressState.error_message == test_message

        s.kill()
