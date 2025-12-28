# =============================================================================
# METHOD 1: Python Runner (Recommended for Cocotb 2.0)
# =============================================================================
# File: run_tests.py

import os
from pathlib import Path

from cocotb_tools.runner import get_runner


def test_axi_pattern_gen():
    """Run the AXI Stream pattern generator tests"""

    # Determine the simulator (tries to auto-detect)
    sim = os.getenv("SIM", "icarus")  # Options: icarus, verilator, questa, vcs, xcelium

    # Get the project root directory
    proj_path = Path(__file__).resolve().parent

    # Verilog source files
    sources = [
        proj_path / "../src/v/axis_tpg.v",
    ]

    # Test module (Python file without .py extension)
    test_module = "test_tpg"

    # Top-level module name in Verilog
    toplevel = "axis_tpg"

    # Create runner
    runner = get_runner(sim)

    # Build arguments (simulator-specific)
    build_args = []
    if sim == "verilator":
        build_args = ["--trace", "--trace-structs"]
    elif sim == "icarus":
        build_args = []

    # Parameters to pass to the DUT
    parameters = {"WIDTH": 256, "HEIGHT": 256, "DATA_WIDTH": 24, "sel_i_WIDTH": 3}

    print("Starting build")

    # Build the design
    runner.build(
        sources=sources,
        hdl_toplevel=toplevel,
        build_args=build_args,
        parameters=parameters,
    )

    # Run the tests
    runner.test(
        hdl_toplevel=toplevel,
        test_module=test_module,
        waves=True,  # Generate waveforms
    )


if __name__ == "__main__":
    test_axi_pattern_gen()
