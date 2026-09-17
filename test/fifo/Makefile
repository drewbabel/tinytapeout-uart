# Isolation test for sync_fifo. Run: make -C test/fifo
SRC_DIR = $(CURDIR)/../../src

all:
	iverilog -g2012 -s sync_fifo_tb -o sim $(SRC_DIR)/sync_fifo.sv sync_fifo_tb.sv
	vvp sim

clean:
	rm -f sim *.vcd
