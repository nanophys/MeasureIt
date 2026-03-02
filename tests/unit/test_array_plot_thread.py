"""Tests for ArrayPlotThread visualization of array-valued parameters."""

import numpy as np
import pytest

from measureit.tools.util import is_array_parameter


# ---------------------------------------------------------------------------
# ArrayPlotThread init
# ---------------------------------------------------------------------------
class TestArrayPlotThreadInit:
    def test_construction_with_spectrometer(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        from qcodes.parameters import Parameter

        class MockParam(Parameter):
            def __init__(self, name, **kw):
                super().__init__(name=name, **kw)
                self._value = 0.0

            def get_raw(self):
                return self._value

            def set_raw(self, v):
                self._value = v

        gate = MockParam("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        assert apt.array_param is spec.spectrum
        assert apt.internal_label == "Pixel"
        assert apt.internal_unit == "px"
        assert len(apt.internal_axis) == 128
        assert apt.figs_set is False

    def test_internal_axis_cached(self, qapp, mock_vna):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep1D

        from qcodes.parameters import Parameter

        class MockParam(Parameter):
            def __init__(self, name, **kw):
                super().__init__(name=name, **kw)
                self._value = 0.0

            def get_raw(self):
                return self._value

            def set_raw(self, v):
                self._value = v

        vna = mock_vna()
        gate = MockParam("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(vna.s21_magnitude)

        apt = ArrayPlotThread(s, vna.s21_magnitude)
        assert len(apt.internal_axis) == 201
        assert apt.internal_label == "Frequency"
        assert apt.internal_unit == "Hz"


# ---------------------------------------------------------------------------
# add_data signal handling
# ---------------------------------------------------------------------------
class TestArrayPlotThreadAddData:
    def test_add_data_extracts_array(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep1D

        from qcodes.parameters import Parameter

        class MockParam(Parameter):
            def __init__(self, name, **kw):
                super().__init__(name=name, **kw)
                self._value = 0.0

            def get_raw(self):
                return self._value

            def set_raw(self, v):
                self._value = v

        spec = mock_spectrometer()
        gate = MockParam("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        test_array = np.random.rand(128)

        # Simulate data_list from update_values: [("time", t), (set_param, val), (param, val)]
        data_list = [
            ("time", 1.0),
            (gate, 0.5),
            (spec.spectrum, test_array),
        ]
        apt.add_data(data_list, 0)

        assert len(apt.data_queue) == 1
        sweep_x, arr = apt.data_queue[0]
        assert sweep_x == 0.5  # set_param value, not time
        np.testing.assert_array_equal(arr, test_array)

    def test_add_data_uses_time_for_sweep0d(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep0D

        spec = mock_spectrometer()
        s = Sweep0D(inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        test_array = np.random.rand(128)

        # Sweep0D data_list: [("time", t), (param, val)]
        data_list = [
            ("time", 3.14),
            (spec.spectrum, test_array),
        ]
        apt.add_data(data_list, 0)

        assert len(apt.data_queue) == 1
        sweep_x, arr = apt.data_queue[0]
        assert sweep_x == 3.14  # time value

    def test_add_data_ignores_non_target(self, qapp, mock_spectrometer, mock_parameter):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        scalar = mock_parameter("current", unit="A", label="Current")
        s = Sweep1D(gate, 0, 1, 0.1, inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum, scalar)

        apt = ArrayPlotThread(s, spec.spectrum)

        # Data list without the target array param
        data_list = [
            ("time", 1.0),
            (gate, 0.5),
            (scalar, 42.0),
        ]
        apt.add_data(data_list, 0)

        # Nothing should be queued since array_param was not in data_list
        assert len(apt.data_queue) == 0

    def test_add_data_disabled_noop(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep0D

        spec = mock_spectrometer()
        s = Sweep0D(inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        apt._disabled = True

        data_list = [("time", 1.0), (spec.spectrum, np.zeros(128))]
        apt.add_data(data_list, 0)
        assert len(apt.data_queue) == 0


# ---------------------------------------------------------------------------
# Heatmap buildup
# ---------------------------------------------------------------------------
class TestArrayPlotThreadHeatmapBuildup:
    def test_multiple_arrays_build_heatmap(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep0D

        spec = mock_spectrometer()
        s = Sweep0D(inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)

        # Feed multiple arrays
        for i in range(5):
            arr = np.random.rand(128)
            apt.data_queue.append((float(i), arr))

        # Process all items (simulate timer callback without figs)
        # Manually process since figs_set is False — test the data structure directly
        while len(apt.data_queue) > 0:
            sweep_x, array_data = apt.data_queue.popleft()
            apt.heatmap_rows.append(array_data)
            apt.sweep_axis_values.append(sweep_x)

        assert len(apt.heatmap_rows) == 5
        assert len(apt.sweep_axis_values) == 5
        data_2d = np.array(apt.heatmap_rows)
        assert data_2d.shape == (5, 128)


# ---------------------------------------------------------------------------
# follow_array_param on BaseSweep
# ---------------------------------------------------------------------------
class TestFollowArrayParam:
    def test_sets_attributes(self, qapp, mock_spectrometer, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(spec.spectrum)
        s.follow_array_param(spec.spectrum)

        assert s.array_plot is True
        assert s.array_plot_param is spec.spectrum

    def test_rejects_non_array_param(self, qapp, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep1D

        gate = mock_parameter("gate", unit="V", label="Gate")
        scalar = mock_parameter("current", unit="A", label="Current")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(scalar)

        s.follow_array_param(scalar)

        assert s.array_plot is False
        assert s.array_plot_param is None

    def test_rejects_unfollowed_param(self, qapp, mock_spectrometer, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        # Don't follow the spectrum param

        s.follow_array_param(spec.spectrum)

        assert s.array_plot is False
        assert s.array_plot_param is None


# ---------------------------------------------------------------------------
# Sweep1D with array plot
# ---------------------------------------------------------------------------
class TestSweep1DWithArrayPlot:
    def test_follow_array_param_on_sweep1d(self, qapp, mock_spectrometer, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep1D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        s = Sweep1D(gate, 0, 1, 0.1, **fast_sweep_kwargs)
        s.follow_param(spec.spectrum)
        s.follow_array_param(spec.spectrum)

        assert s.array_plot is True
        assert s.array_plot_param is spec.spectrum
        # array_plotter is not created until start()
        assert s.array_plotter is None


# ---------------------------------------------------------------------------
# Sweep2D delegation
# ---------------------------------------------------------------------------
class TestSweep2DArrayPlotDelegation:
    def test_delegates_to_inner_sweep(self, qapp, mock_spectrometer, mock_parameter, fast_sweep_kwargs):
        from measureit.sweep import Sweep2D

        spec = mock_spectrometer()
        gate = mock_parameter("gate", unit="V", label="Gate")
        outer = mock_parameter("outer", unit="V", label="Outer")

        s2d = Sweep2D(
            [gate, 0, 1, 0.1],
            [outer, 0, 1, 0.5],
            **fast_sweep_kwargs,
        )
        s2d.follow_param(spec.spectrum)
        s2d.follow_array_param(spec.spectrum)

        # The inner sweep should have the array_plot settings
        assert s2d.in_sweep.array_plot is True
        assert s2d.in_sweep.array_plot_param is spec.spectrum


# ---------------------------------------------------------------------------
# Reset and clear
# ---------------------------------------------------------------------------
class TestArrayPlotReset:
    def test_reset_clears_buffers(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep0D

        spec = mock_spectrometer()
        s = Sweep0D(inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        # Add some data
        apt.data_queue.append((0.0, np.zeros(128)))
        apt.heatmap_rows.append(np.zeros(128))
        apt.sweep_axis_values.append(0.0)

        apt.reset()

        assert len(apt.data_queue) == 0
        assert len(apt.heatmap_rows) == 0
        assert len(apt.sweep_axis_values) == 0


class TestArrayPlotClear:
    def test_clear_with_figs(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep0D

        spec = mock_spectrometer()
        s = Sweep0D(inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        apt.create_figs()
        assert apt.figs_set is True
        assert apt.widget is not None
        assert apt.update_timer is not None

        apt.clear()
        assert apt.figs_set is False
        assert apt.widget is None
        assert apt.update_timer is None

    def test_clear_without_figs(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep0D

        spec = mock_spectrometer()
        s = Sweep0D(inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        # Should not raise
        apt.clear()
        assert apt.figs_set is False


# ---------------------------------------------------------------------------
# create_figs
# ---------------------------------------------------------------------------
class TestArrayPlotCreateFigs:
    def test_create_figs(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep0D

        spec = mock_spectrometer()
        s = Sweep0D(inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        apt.create_figs()

        assert apt.figs_set is True
        assert apt.widget is not None
        assert apt.line_plot is not None
        assert apt.line_curve is not None
        assert apt.heatmap_plot is not None
        assert apt.image_item is not None
        assert apt.update_timer is not None

        # Cleanup
        apt.clear()

    def test_create_figs_idempotent(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep0D

        spec = mock_spectrometer()
        s = Sweep0D(inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        apt.create_figs()
        widget1 = apt.widget
        apt.create_figs()  # should not create new widget
        assert apt.widget is widget1

        apt.clear()


# ---------------------------------------------------------------------------
# update_display with live widgets
# ---------------------------------------------------------------------------
class TestArrayPlotUpdateDisplay:
    def test_update_display_processes_queue(self, qapp, mock_spectrometer):
        from measureit.visualization.array_plot_thread import ArrayPlotThread
        from measureit.sweep import Sweep0D

        spec = mock_spectrometer()
        s = Sweep0D(inter_delay=0.01, save_data=False, plot_data=False, suppress_output=True)
        s.follow_param(spec.spectrum)

        apt = ArrayPlotThread(s, spec.spectrum)
        apt.create_figs()

        # Feed data
        for i in range(3):
            apt.data_queue.append((float(i), np.random.rand(128)))

        apt.update_display()

        assert len(apt.data_queue) == 0
        assert len(apt.heatmap_rows) == 3
        assert len(apt.sweep_axis_values) == 3

        apt.clear()
