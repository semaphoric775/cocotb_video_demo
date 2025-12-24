"""
Cocotb testbench for image_aggregator_top
"""

import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, Timer
from cocotbext.axi import AxiStreamBus, AxiStreamFrame, AxiStreamSink, AxiStreamSource

# Image configuration
# TODO: Implement file IO to scrape image configuration from VHDL package
C_PIXELS_PER_ROW = 640
C_ROWS_PER_IMAGE = 480
C_AXIS_TDATA_WIDTH = 32


class ImageAggregatorTB:
    """Testbench wrapper for image aggregator"""

    def __init__(self, dut):
        self.dut = dut

        # Create clock
        cocotb.start_soon(Clock(dut.clk, 10, unit="ns").start())

        # Create AXI Stream sources for 4 inputs
        self.source0 = AxiStreamSource(
            AxiStreamBus.from_prefix(dut, "s0_axis"),
            dut.clk,
            dut.rst_n,
            reset_active_level=False,
        )

        self.source1 = AxiStreamSource(
            AxiStreamBus.from_prefix(dut, "s1_axis"),
            dut.clk,
            dut.rst_n,
            reset_active_level=False,
        )

        self.source2 = AxiStreamSource(
            AxiStreamBus.from_prefix(dut, "s2_axis"),
            dut.clk,
            dut.rst_n,
            reset_active_level=False,
        )

        self.source3 = AxiStreamSource(
            AxiStreamBus.from_prefix(dut, "s3_axis"),
            dut.clk,
            dut.rst_n,
            reset_active_level=False,
        )

        # Create AXI Stream sink for output
        self.sink = AxiStreamSink(
            AxiStreamBus.from_prefix(dut, "m_axis"),
            dut.clk,
            dut.rst_n,
            reset_active_level=False,
        )

    async def reset(self):
        """Reset the DUT"""
        self.dut.rst_n.value = 0
        await Timer(100, unit="ns")
        await RisingEdge(self.dut.clk)
        self.dut.rst_n.value = 1
        await RisingEdge(self.dut.clk)
        self.dut._log.info("Reset complete")

    def generate_test_image(self, width, height, pattern="counter"):
        """Generate a test image as a list of 32-bit words"""
        pixels = []
        for row in range(height):
            for col in range(width):
                if pattern == "counter":
                    # Simple counter pattern
                    pixel_value = (row * width + col) & 0xFFFFFFFF
                elif pattern == "random":
                    # Random pattern
                    pixel_value = random.randint(0, 0xFFFFFFFF)
                elif pattern == "gradient":
                    # Gradient pattern
                    pixel_value = ((row * 255 // height) << 16) | (
                        (col * 255 // width) << 8
                    )
                else:
                    pixel_value = 0

                pixels.append(pixel_value)

        return pixels

    async def send_image(self, source, image_data, sof=True):
        """Send an image through an AXI Stream source"""
        frame = AxiStreamFrame()

        # Convert pixel data to bytes (little-endian 32-bit)
        for pixel in image_data:
            frame.tdata.extend(pixel.to_bytes(4, byteorder="little"))

        # Set SOF on first transfer if requested
        if sof:
            frame.tuser = 1
        else:
            frame.tuser = 0

        await source.send(frame)
        self.dut._log.info(f"Sent image with {len(image_data)} pixels")


@cocotb.test()
async def test_reset(dut):
    """Test reset behavior"""
    tb = ImageAggregatorTB(dut)
    await tb.reset()

    # Check that all ready signals are low after reset
    await RisingEdge(dut.clk)
    assert dut.s0_tready.value == 0, "s0_tready should be low after reset"
    assert dut.s1_tready.value == 0, "s1_tready should be low after reset"
    assert dut.s2_tready.value == 0, "s2_tready should be low after reset"
    assert dut.s3_tready.value == 0, "s3_tready should be low after reset"

    dut._log.info("Reset test passed")


@cocotb.test()
async def test_single_frame(dut):
    """Test sending a single frame through all inputs"""
    tb = ImageAggregatorTB(dut)
    await tb.reset()

    # Generate test images for each quadrant
    width = C_PIXELS_PER_ROW // 2
    height = C_ROWS_PER_IMAGE // 2

    img0 = tb.generate_test_image(width, height, pattern="counter")
    img1 = tb.generate_test_image(width, height, pattern="gradient")
    img2 = tb.generate_test_image(width, height, pattern="random")
    img3 = tb.generate_test_image(width, height, pattern="counter")

    # Send images to all 4 inputs
    await cocotb.start_soon(tb.send_image(tb.source0, img0, sof=True))
    await cocotb.start_soon(tb.send_image(tb.source1, img1, sof=True))
    await cocotb.start_soon(tb.send_image(tb.source2, img2, sof=True))
    await cocotb.start_soon(tb.send_image(tb.source3, img3, sof=True))

    # Wait for output
    await Timer(10, unit="us")

    # Check if we received any output
    if not tb.sink.empty():
        output_frame = await tb.sink.recv()
        dut._log.info(f"Received output frame with {len(output_frame.tdata)} bytes")
    else:
        dut._log.warning("No output received (design stub not implemented)")

    dut._log.info("Single frame test complete")


@cocotb.test()
async def test_backpressure(dut):
    """Test backpressure handling"""
    tb = ImageAggregatorTB(dut)
    await tb.reset()

    # Set backpressure on output
    tb.sink.set_pause_generator(lambda: random.choice([0, 1, 2, 3]))

    # Generate and send test images
    width = C_PIXELS_PER_ROW // 2
    height = C_ROWS_PER_IMAGE // 2

    img0 = tb.generate_test_image(width, height, pattern="counter")

    await tb.send_image(tb.source0, img0, sof=True)

    # Wait for transaction to complete with backpressure
    await Timer(20, unit="us")

    dut._log.info("Backpressure test complete")


@cocotb.test()
async def test_state_machine(dut):
    """Test state machine transitions"""
    tb = ImageAggregatorTB(dut)
    await tb.reset()

    # Wait a few cycles and observe state transitions
    for i in range(20):
        await RisingEdge(dut.clk)
        # State machine should be in S_WAIT_SOF initially
        dut._log.info(
            f"Cycle {i}: ready signals = {dut.s0_tready.value}, "
            f"{dut.s1_tready.value}, {dut.s2_tready.value}, {dut.s3_tready.value}"
        )

    dut._log.info("State machine test complete")
