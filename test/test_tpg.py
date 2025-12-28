import random
from pathlib import Path

import cocotb
import matplotlib.pyplot as plt
import numpy as np
from cocotb.clock import Clock
from cocotb.triggers import ClockCycles, RisingEdge
from cocotb.types import LogicArray


class AXIStreamMonitor:
    """Monitor for AXI Stream interface"""

    def __init__(self, dut, name="axis"):
        self.dut = dut
        self.name = name
        self.received_frames = []
        self.current_frame = []

    async def monitor(self):
        """Monitor AXI Stream transactions"""
        while True:
            await RisingEdge(self.dut.clk_i)

            if self.dut.m_axis_tvalid_o.value and self.dut.m_axis_tready_i.value:
                pixel_data = int(self.dut.m_axis_tdata_o.value)
                tlast = int(self.dut.m_axis_tlast_o.value)
                tuser = int(self.dut.m_axis_tuser_o.value)

                pixel_info = {"data": pixel_data, "tlast": tlast, "tuser": tuser}

                self.current_frame.append(pixel_info)

                # Check for end of frame (last pixel)
                if tlast and len(self.current_frame) > 0:
                    # Check if this is the last line
                    lines = []
                    current_line = []
                    for p in self.current_frame:
                        current_line.append(p)
                        if p["tlast"]:
                            lines.append(current_line)
                            current_line = []

                    # If we have a complete frame, save it
                    if len(lines) > 0:
                        self.received_frames.append(lines)

                        # Check if frame is complete (last line's last pixel)
                        total_pixels = sum(len(line) for line in lines)
                        expected_pixels = self.dut.WIDTH.value * self.dut.HEIGHT.value

                        if total_pixels >= expected_pixels:
                            self.current_frame = []


async def reset_dut(dut):
    """Reset the DUT"""
    dut.rstn_i.value = 0
    dut.en_i.value = 0
    dut.sel_i.value = 0
    dut.m_axis_tready_i.value = 1
    await ClockCycles(dut.clk_i, 5)
    dut.rstn_i.value = 1
    await ClockCycles(dut.clk_i, 2)


async def apply_backpressure(dut, pattern="random", probability=0.3):
    """Apply backpressure to tready signal"""
    while True:
        await RisingEdge(dut.clk_i)
        if pattern == "random":
            dut.m_axis_tready_i.value = 1 if random.random() > probability else 0
        elif pattern == "every_other":
            current = dut.m_axis_tready_i.value
            dut.m_axis_tready_i.value = 0 if current else 1
        else:  # always ready
            dut.m_axis_tready_i.value = 1


@cocotb.test()
async def test_colorbar_pattern(dut):
    """Test colorbar pattern and visualize with matplotlib"""

    clock = Clock(dut.clk_i, 10, unit="ns")
    cocotb.start_soon(clock.start())

    await reset_dut(dut)

    dut.m_axis_tready_i.value = 1
    dut.sel_i.value = 1  # Color bars
    dut.en_i.value = 1

    await ClockCycles(dut.clk_i, 2)

    # Get frame dimensions
    width = int(dut.WIDTH.value)
    height = int(dut.HEIGHT.value)
    data_width = int(dut.DATA_WIDTH.value)

    dut._log.info(f"Capturing frame: {width}x{height}, {data_width}-bit data")

    # Create array to store the frame
    frame = np.zeros((height + 1, width + 1, 3), dtype=np.uint8)

    # Capture entire frame
    pixel_count = 0
    x = 0
    y = 0

    while y < height:
        await RisingEdge(dut.clk_i)

        if dut.m_axis_tvalid_o.value and dut.m_axis_tready_i.value:
            # Get pixel data
            pixel_data = int(dut.m_axis_tdata_o.value)

            # Extract RGB channels (assuming RGB888: [R7:R0, G7:G0, B7:B0])
            r = (pixel_data >> 16) & 0xFF
            g = (pixel_data >> 8) & 0xFF
            b = pixel_data & 0xFF

            # Store in frame array
            frame[y, x] = [r, g, b]

            pixel_count += 1

            # Handle line wrapping
            if dut.m_axis_tlast_o.value:
                x = 0
                y += 1
            else:
                x += 1

    dut._log.info(f"Captured {pixel_count} pixels ({width}x{height})")

    # Verify we got different colors
    unique_colors = len(np.unique(frame.reshape(-1, 3), axis=0))
    assert unique_colors > 1, (
        f"Color bar should have multiple colors, got {unique_colors}"
    )

    dut._log.info(f"Found {unique_colors} unique colors")

    # Create output directory
    output_dir = Path("test_results")
    output_dir.mkdir(exist_ok=True)

    # Create visualization
    fig, axes = plt.subplots(2, 2, figsize=(12, 10))
    fig.suptitle(
        "AXI Stream Color Bar Pattern Analysis", fontsize=16, fontweight="bold"
    )

    # 1. Full frame
    axes[0, 0].imshow(frame)
    axes[0, 0].set_title(f"Full Frame ({width}x{height})")
    axes[0, 0].axis("off")

    # 2. First line profile
    first_line = frame[0, :, :]
    axes[0, 1].imshow(first_line[np.newaxis, :, :], aspect="auto")
    axes[0, 1].set_title("First Line (Horizontal Slice)")
    axes[0, 1].set_xlabel("X Position")
    axes[0, 1].set_yticks([])

    # 3. RGB channel values along first line
    axes[1, 0].plot(first_line[:, 0], "r-", label="Red", linewidth=2)
    axes[1, 0].plot(first_line[:, 1], "g-", label="Green", linewidth=2)
    axes[1, 0].plot(first_line[:, 2], "b-", label="Blue", linewidth=2)
    axes[1, 0].set_title("RGB Channel Values (First Line)")
    axes[1, 0].set_xlabel("X Position (pixels)")
    axes[1, 0].set_ylabel("Channel Value (0-255)")
    axes[1, 0].legend()
    axes[1, 0].grid(True, alpha=0.3)
    axes[1, 0].set_ylim(-10, 265)

    # 4. Color bar identification
    # Detect color transitions
    color_changes = []
    for i in range(1, width):
        if not np.array_equal(first_line[i], first_line[i - 1]):
            color_changes.append(i)

    num_bars = len(color_changes) + 1

    # Extract unique colors from first line
    bar_colors = []
    bar_positions = [0] + color_changes + [width]

    for i in range(len(bar_positions) - 1):
        start = bar_positions[i]
        end = bar_positions[i + 1]
        mid = (start + end) // 2
        color = first_line[mid] / 255.0  # Normalize for matplotlib
        bar_colors.append(color)

    # Plot color bars
    for i, (start, end, color) in enumerate(
        zip(bar_positions[:-1], bar_positions[1:], bar_colors)
    ):
        width_px = end - start
        axes[1, 1].barh(
            0,
            width_px,
            left=start,
            height=0.8,
            color=color,
            edgecolor="black",
            linewidth=1.5,
        )

        # Add text label
        mid = (start + end) / 2
        color_hex = "#{:02x}{:02x}{:02x}".format(
            int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
        )
        axes[1, 1].text(
            mid,
            0,
            f"Bar {i + 1}\n{color_hex}",
            ha="center",
            va="center",
            fontsize=8,
            fontweight="bold",
        )

    axes[1, 1].set_title(f"Detected Color Bars (n={num_bars})")
    axes[1, 1].set_xlabel("X Position (pixels)")
    axes[1, 1].set_xlim(0, width)
    axes[1, 1].set_ylim(-0.5, 0.5)
    axes[1, 1].set_yticks([])

    plt.tight_layout()

    # Save figure
    output_file = output_dir / "colorbar_pattern_analysis.png"
    plt.savefig(output_file, dpi=150, bbox_inches="tight")
    dut._log.info(f"Visualization saved to: {output_file}")

    # Also save raw frame data
    frame_file = output_dir / "colorbar_frame.npy"
    np.save(frame_file, frame)
    dut._log.info(f"Raw frame data saved to: {frame_file}")

    # Optional: Display plot (comment out for CI/CD environments)
    plt.show()

    # plt.close()

    # Print summary statistics
    dut._log.info("=" * 60)
    dut._log.info("COLORBAR PATTERN ANALYSIS SUMMARY")
    dut._log.info("=" * 60)
    dut._log.info(f"Frame Size: {width}x{height} pixels")
    dut._log.info(f"Total Pixels: {pixel_count}")
    dut._log.info(f"Unique Colors: {unique_colors}")
    dut._log.info(f"Number of Color Bars: {num_bars}")
    dut._log.info(f"Pixels per Bar: ~{width // num_bars}")

    for i, color in enumerate(bar_colors):
        rgb = tuple(int(c * 255) for c in color)
        dut._log.info(f"  Bar {i + 1}: RGB{rgb}")

    dut._log.info("=" * 60)

    dut._log.info(f"✓ Colorbar visualization test passed")
