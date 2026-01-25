"""Unit tests for Heatmap axis orientation in Sweep2D.

This test verifies that the x and y axes in the heatmap correctly correspond
to the inner and outer sweep parameters respectively.
"""

import numpy as np
import pytest


class TestHeatmapAxisOrientation:
    """Test that heatmap data is correctly oriented with respect to sweep axes."""

    def test_data_row_corresponds_to_outer_sweep_value(self, mock_parameters, fast_sweep_kwargs, qapp):
        """Test that data for a given outer sweep value is placed in the correct row.

        The heatmap should display:
        - X axis (horizontal): inner sweep parameter values
        - Y axis (vertical): outer sweep parameter values

        When data is collected at out_value = out_start (first outer step),
        it should appear at the bottom of the heatmap (row 0 in the data array
        when using PyQtGraph's default coordinate system with setRect).

        Bug: Currently the row index is inverted, causing out_start data to
        appear at out_stop position and vice versa.
        """
        from measureit.sweep.sweep2d import Sweep2D
        from measureit.visualization.heatmap_thread import Heatmap

        # Create a sweep with known parameters
        # Inner sweep: voltage from 0 to 1 with step 0.5 (3 points: 0, 0.5, 1)
        # Outer sweep: gate from -1 to 1 with step 1.0 (3 points: -1, 0, 1)
        in_params = [mock_parameters["voltage"], 0, 1, 0.5]
        out_params = [mock_parameters["gate"], -1, 1, 1.0]

        sweep = Sweep2D(
            in_params,
            out_params,
            outer_delay=0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        # Create heatmap and initialize its data structures
        heatmap = Heatmap(sweep)

        # Manually initialize the heatmap data structures (simulating create_figs)
        heatmap.res_in = 3  # 0, 0.5, 1
        heatmap.res_out = 3  # -1, 0, 1
        heatmap.in_keys = [0.0, 0.5, 1.0]
        heatmap.out_keys = [-1.0, 0.0, 1.0]
        heatmap.in_step = 0.5
        heatmap.out_step = 1.0
        heatmap.figs_set = True
        heatmap.param_surfaces = {}

        # Create a data dict to simulate data from the plotter
        # This represents completing an inner sweep at outer value = -1.0 (out_start)
        # The measurement values are [10, 20, 30] at inner values [0, 0.5, 1.0]
        data_dict = {
            "forward": (
                np.array([0.0, 0.5, 1.0]),  # x_data (inner sweep values)
                np.array([10.0, 20.0, 30.0]),  # y_data (measured values)
            ),
            "param_index": 1,  # Index of the parameter being measured
            "out_value": -1.0,  # This is out_start
        }

        # Add the data to the heatmap
        heatmap.add_to_heatmap(data_dict)

        # Get the data array for this parameter
        data_array = heatmap.param_surfaces[1]["data"]

        # The data array has shape (res_out, res_in) = (3, 3)
        # Rows correspond to outer sweep values, columns to inner sweep values
        #
        # With setRect mapping:
        # - Row 0 should correspond to out_start = -1.0 (bottom of y-axis)
        # - Row 2 should correspond to out_stop = 1.0 (top of y-axis)
        #
        # So data collected at out_value = -1.0 should be in row 0.

        # Verify the data is in row 0 (corresponding to out_start = -1.0)
        # This is where the bug manifests: currently the data ends up in row 2
        expected_row = 0  # out_start should map to row 0

        # Check that row 0 contains the data we added
        assert data_array[expected_row, 0] == 10.0, \
            f"Data at (row=0, col=0) should be 10.0 but got {data_array[expected_row, 0]}. " \
            f"Row 0 should contain data for out_value=-1.0 (out_start)."
        assert data_array[expected_row, 1] == 20.0, \
            f"Data at (row=0, col=1) should be 20.0 but got {data_array[expected_row, 1]}."
        assert data_array[expected_row, 2] == 30.0, \
            f"Data at (row=0, col=2) should be 30.0 but got {data_array[expected_row, 2]}."

        # Also verify that other rows are still zero (data should NOT be in row 2)
        assert data_array[2, 0] == 0.0, \
            f"Row 2 should be empty but contains {data_array[2, 0]}. " \
            f"Bug: data for out_start is incorrectly placed at out_stop row."

    def test_multiple_outer_steps_correct_row_mapping(self, mock_parameters, fast_sweep_kwargs, qapp):
        """Test that multiple outer sweep steps map to correct rows.

        For a sweep with outer values [-1, 0, 1]:
        - out_value = -1 (out_start) should map to row 0 (bottom)
        - out_value = 0 should map to row 1 (middle)
        - out_value = 1 (out_stop) should map to row 2 (top)
        """
        from measureit.sweep.sweep2d import Sweep2D
        from measureit.visualization.heatmap_thread import Heatmap

        in_params = [mock_parameters["voltage"], 0, 1, 0.5]
        out_params = [mock_parameters["gate"], -1, 1, 1.0]

        sweep = Sweep2D(
            in_params,
            out_params,
            outer_delay=0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        heatmap = Heatmap(sweep)
        heatmap.res_in = 3
        heatmap.res_out = 3
        heatmap.in_keys = [0.0, 0.5, 1.0]
        heatmap.out_keys = [-1.0, 0.0, 1.0]
        heatmap.in_step = 0.5
        heatmap.out_step = 1.0
        heatmap.figs_set = True
        heatmap.param_surfaces = {}

        # Add data for each outer sweep step with distinguishable values
        test_cases = [
            {"out_value": -1.0, "values": [100.0, 110.0, 120.0], "expected_row": 0},
            {"out_value": 0.0, "values": [200.0, 210.0, 220.0], "expected_row": 1},
            {"out_value": 1.0, "values": [300.0, 310.0, 320.0], "expected_row": 2},
        ]

        for case in test_cases:
            data_dict = {
                "forward": (
                    np.array([0.0, 0.5, 1.0]),
                    np.array(case["values"]),
                ),
                "param_index": 1,
                "out_value": case["out_value"],
            }
            heatmap.add_to_heatmap(data_dict)

        data_array = heatmap.param_surfaces[1]["data"]

        # Verify each row contains the correct data
        for case in test_cases:
            row = case["expected_row"]
            expected_values = case["values"]
            actual_values = [data_array[row, 0], data_array[row, 1], data_array[row, 2]]

            assert actual_values == expected_values, \
                f"Row {row} (out_value={case['out_value']}) should contain {expected_values} " \
                f"but got {actual_values}. The y-axis mapping is inverted."

    def test_inner_sweep_maps_to_columns(self, mock_parameters, fast_sweep_kwargs, qapp):
        """Test that inner sweep values correctly map to columns (x-axis).

        For inner sweep values [0, 0.5, 1.0]:
        - in_value = 0 should map to column 0 (left)
        - in_value = 0.5 should map to column 1 (middle)
        - in_value = 1.0 should map to column 2 (right)
        """
        from measureit.sweep.sweep2d import Sweep2D
        from measureit.visualization.heatmap_thread import Heatmap

        in_params = [mock_parameters["voltage"], 0, 1, 0.5]
        out_params = [mock_parameters["gate"], -1, 1, 1.0]

        sweep = Sweep2D(
            in_params,
            out_params,
            outer_delay=0.1,
            **fast_sweep_kwargs,
        )
        sweep.follow_param(mock_parameters["current"])

        heatmap = Heatmap(sweep)
        heatmap.res_in = 3
        heatmap.res_out = 3
        heatmap.in_keys = [0.0, 0.5, 1.0]
        heatmap.out_keys = [-1.0, 0.0, 1.0]
        heatmap.in_step = 0.5
        heatmap.out_step = 1.0
        heatmap.figs_set = True
        heatmap.param_surfaces = {}

        # Add data with specific values to verify column mapping
        # Value at each position uniquely identifies its (in_value, out_value) pair
        data_dict = {
            "forward": (
                np.array([0.0, 0.5, 1.0]),  # Inner sweep x values
                np.array([1.0, 2.0, 3.0]),  # Measurement values
            ),
            "param_index": 1,
            "out_value": 0.0,  # Middle row
        }
        heatmap.add_to_heatmap(data_dict)

        data_array = heatmap.param_surfaces[1]["data"]

        # The expected row for out_value=0.0 is row 1 (middle)
        # But due to the bug, it might be in a different row
        # Let's check column mapping is correct regardless of which row the data is in

        # Find which row has non-zero data
        non_zero_rows = np.where(np.any(data_array != 0, axis=1))[0]
        assert len(non_zero_rows) == 1, \
            f"Expected exactly one row with data, found {len(non_zero_rows)}"

        data_row = non_zero_rows[0]

        # Verify column mapping: column 0 should have value 1.0, column 1 should have 2.0, etc.
        assert data_array[data_row, 0] == 1.0, \
            f"Column 0 (in_value=0.0) should have value 1.0, got {data_array[data_row, 0]}"
        assert data_array[data_row, 1] == 2.0, \
            f"Column 1 (in_value=0.5) should have value 2.0, got {data_array[data_row, 1]}"
        assert data_array[data_row, 2] == 3.0, \
            f"Column 2 (in_value=1.0) should have value 3.0, got {data_array[data_row, 2]}"
