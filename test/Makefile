# Makefile for cocotb simulation of image_aggregator_top

# Simulator
SIM ?= ghdl

# VHDL source files
VHDL_SOURCES = $(PWD)/../src/image_aggregator_pkg.vhd \
               $(PWD)/../src/image_aggregator_top.vhd

# Python test module
COCOTB_TEST_MODULES = test_image_aggregator

# Toplevel module
COCOTB_TOPLEVEL = image_aggregator_top

# GHDL specific arguments
EXTRA_ARGS += --ieee=synopsys --std=08

# Include cocotb's make rules
include $(shell cocotb-config --makefiles)/Makefile.sim

# Clean target
clean::
	rm -rf __pycache__
	rm -rf sim_build
	rm -f results.xml
	rm -f *.vcd *.ghw *.o image_aggregator_top
