# Isolation test for apb_csr. Run: make -C test/csr
SIM ?= icarus
TOPLEVEL_LANG ?= verilog
SRC_DIR = $(PWD)/../../src

VERILOG_SOURCES += $(SRC_DIR)/apb_csr.sv
VERILOG_SOURCES += $(PWD)/tb_csr.sv

TOPLEVEL = tb_csr
COCOTB_TEST_MODULES = test_csr

include $(shell cocotb-config --makefiles)/Makefile.sim
