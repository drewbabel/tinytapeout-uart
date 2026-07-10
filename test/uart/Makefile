# uart feature tests (parity + runtime baud). Run: make -C test/uart
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../../src

VERILOG_SOURCES += $(SRC_DIR)/synchronizer.sv
VERILOG_SOURCES += $(SRC_DIR)/tick_gen.sv
VERILOG_SOURCES += $(SRC_DIR)/parity.sv
VERILOG_SOURCES += $(SRC_DIR)/uart_tx.sv
VERILOG_SOURCES += $(SRC_DIR)/uart_rx.sv
VERILOG_SOURCES += $(SRC_DIR)/uart.sv
VERILOG_SOURCES += $(PWD)/tb_uart.sv

TOPLEVEL = tb_uart
COCOTB_TEST_MODULES = test_uart

include $(shell cocotb-config --makefiles)/Makefile.sim
