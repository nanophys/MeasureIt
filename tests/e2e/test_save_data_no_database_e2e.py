"""End-to-end test for bug: sweep stalls when save_data=True but no database is registered.

This test reproduces the actual bug behavior by using real Qt/QCoDeS (not fake stubs)
to demonstrate that when save_data=True without a registered database, the sweep
enters a running state and stalls (measurement does not progress).
"""

import time
import pytest

import qcodes as qc
from qcodes.instrument_drivers.mock_instruments import MockParabola

from measureit.sweep.sweep1d import Sweep1D
from measureit.sweep.progress import SweepState


@pytest.fixture
def mock_parabola_no_db():
    """Create a MockParabola instrument without database initialization."""
    # Close any existing instruments first
    try:
        qc.Instrument.close_all()
    except:
        pass

    instr = MockParabola(name="test_parabola_no_db")
    instr.noise.set(1)
    instr.parabola.label = "Test Parabola"

    yield instr

    time.sleep(0.3)
    try:
        instr.close()
    except:
        pass


@pytest.mark.e2e
class TestSaveDataNoDatabaseBugE2E:
    """End-to-end tests to reproduce the save_data=True without database bug."""

    def test_sweep_stalls_with_save_data_no_database(self, mock_parabola_no_db, temp_measureit_home, qtbot):
        """Test that sweep stalls when save_data=True but no database is registered.

        This test reproduces the bug where:
        1. save_data=True is set
        2. No database is registered/initialized via init_database()
        3. The sweep enters RUNNING state but measurement doesn't progress
           because meas.run() in runner_thread.py fails

        Expected behavior after fix:
        - The sweep should either fail fast with a clear error message
        - Or gracefully handle the missing database
        """
        # Capture Qt exceptions - the bug causes an unhandled ValueError in runner thread
        with qtbot.capture_exceptions() as exceptions:
            sweep = Sweep1D(
                mock_parabola_no_db.x,
                start=0,
                stop=1,
                step=0.5,
                inter_delay=0.05,
                save_data=True,  # Key: save_data is True but no database
                plot_data=False,
                suppress_output=True,
            )
            sweep.follow_param(mock_parabola_no_db.parabola)

            # Track completion
            completed = []
            error_messages = []

            def on_completed():
                completed.append(True)

            def on_print(msg):
                error_messages.append(msg)

            sweep.completed.connect(on_completed)
            sweep.print_main.connect(on_print)

            # Start sweep WITHOUT initializing a database
            # This should trigger the bug: sweep enters RUNNING but stalls
            sweep.start(ramp_to_start=False)

            # Wait to see if sweep progresses or stalls
            # The bug causes it to stall here, so we use a timeout
            timeout = 3.0
            start_time = time.time()
            while sweep.check_running() and (time.time() - start_time) < timeout:
                time.sleep(0.1)

            # Record final state
            final_state = sweep.progressState.state
            was_running = sweep.check_running() or final_state == SweepState.RUNNING

            # Cleanup
            sweep.kill()
            time.sleep(0.3)

        # The bug manifests as:
        # - State transitions to RUNNING
        # - But no actual progress (no data points taken)
        # - Either stalls forever or silently fails

        # Document current (buggy) behavior
        print(f"Final state: {final_state}")
        print(f"Was still running at timeout: {was_running}")
        print(f"Completed signal received: {len(completed) > 0}")
        print(f"Error messages: {error_messages}")
        print(f"Qt exceptions captured: {len(exceptions)}")

        # Verify the bug: an exception was raised in the Qt event loop
        # This confirms the runner thread crashed due to missing database
        assert len(exceptions) > 0, (
            "Bug reproduction: Expected Qt exception from runner thread, but none captured"
        )

        # Verify the exception is about missing experiment/database
        exception_msgs = [str(e) for e in exceptions]
        has_db_error = any(
            "experiment" in msg.lower() or "database" in msg.lower()
            for msg in exception_msgs
        )
        assert has_db_error, (
            f"Bug reproduction: Expected exception about missing experiment/database, "
            f"got: {exception_msgs}"
        )

        # Bug is confirmed if sweep stalls in RUNNING state
        # Test passes to document that the bug exists
        assert final_state == SweepState.RUNNING, (
            f"Bug reproduction: Expected sweep to stall in RUNNING state, "
            f"but got {final_state}. Messages: {error_messages}"
        )

    def test_sweep_works_without_database_when_save_data_false(
        self, mock_parabola_no_db, temp_measureit_home
    ):
        """Verify sweep works when save_data=False (no database needed).

        This test confirms that the bug is specific to save_data=True.
        """
        sweep = Sweep1D(
            mock_parabola_no_db.x,
            start=0,
            stop=0.5,
            step=0.25,
            inter_delay=0.05,
            save_data=False,  # No database needed
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parabola_no_db.parabola)

        completed = []
        sweep.completed.connect(lambda: completed.append(True))

        sweep.start(ramp_to_start=False)

        # This should complete without issues
        timeout = 5.0
        start_time = time.time()
        while sweep.check_running() and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        final_state = sweep.progressState.state
        sweep.kill()
        time.sleep(0.3)

        # Should complete successfully
        assert final_state in (SweepState.DONE, SweepState.KILLED), \
            f"Expected DONE or KILLED, got {final_state}"

    def test_sweep_works_with_database_when_save_data_true(
        self, mock_parabola_no_db, temp_database
    ):
        """Verify sweep works when save_data=True AND database is properly initialized.

        This test confirms normal operation when database is set up correctly.
        """
        from measureit.tools.util import init_database

        sweep = Sweep1D(
            mock_parabola_no_db.x,
            start=0,
            stop=0.5,
            step=0.25,
            inter_delay=0.05,
            save_data=True,
            plot_data=False,
            suppress_output=True,
        )
        sweep.follow_param(mock_parabola_no_db.parabola)

        # Initialize database properly
        init_database(str(temp_database), "test_exp", "test_sample", sweep)

        completed = []
        sweep.completed.connect(lambda: completed.append(True))

        sweep.start(ramp_to_start=False)

        # Should complete successfully
        timeout = 5.0
        start_time = time.time()
        while sweep.check_running() and (time.time() - start_time) < timeout:
            time.sleep(0.1)

        final_state = sweep.progressState.state
        sweep.kill()
        time.sleep(0.3)

        # Should complete successfully and save data
        assert final_state in (SweepState.DONE, SweepState.KILLED), \
            f"Expected DONE or KILLED, got {final_state}"

        # Verify data was saved
        dataset = qc.load_by_id(1)
        assert dataset.number_of_results > 0
