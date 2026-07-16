# GATES=yes for gate level

SIM ?= icarus
FST ?= -fst
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../../src
PROJECT_SOURCES = project.sv
PROJECT_SOURCES += uart.sv
PROJECT_SOURCES += uart_tx.sv
PROJECT_SOURCES += uart_rx.sv
PROJECT_SOURCES += tick_gen.sv
PROJECT_SOURCES += synchronizer.sv
PROJECT_SOURCES += sync_fifo.sv
PROJECT_SOURCES += parity.sv
PROJECT_SOURCES += apb_csr.sv
PROJECT_SOURCES += csr_pin_adapter.sv

ifneq ($(GATES),yes)

SIM_BUILD = sim_build/rtl
VERILOG_SOURCES += $(addprefix $(SRC_DIR)/,$(PROJECT_SOURCES))

else

SIM_BUILD = sim_build/gl
COMPILE_ARGS += -DGL_TEST
COMPILE_ARGS += -DFUNCTIONAL
COMPILE_ARGS += -DUSE_POWER_PINS
COMPILE_ARGS += -DSIM
COMPILE_ARGS += -DUNIT_DELAY=\#1
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/primitives.v
VERILOG_SOURCES += $(PDK_ROOT)/sky130A/libs.ref/sky130_fd_sc_hd/verilog/sky130_fd_sc_hd.v
VERILOG_SOURCES += $(PWD)/../gate_level_netlist.v

endif

COMPILE_ARGS += -I$(SRC_DIR)
VERILOG_SOURCES += $(PWD)/../tb.sv
TOPLEVEL = tb

COCOTB_TEST_MODULES = test_harness

include $(shell cocotb-config --makefiles)/Makefile.sim
