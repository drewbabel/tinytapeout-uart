// Generates uart_csr_wave.csv for the README CSR-write waveform. Throwaway.
//   iverilog -g2012 -s uart_csr_wave_tb -o w.vvp ../src/synchronizer.sv ../src/apb_csr.sv ../src/csr_pin_adapter.sv uart_csr_wave_tb.sv && vvp w.vvp
//   python3 uart_csr_waveform.py
`timescale 1ns / 1ps

module uart_csr_wave_tb;
  localparam int ADDR_W = 3;
  localparam int DATA_W = 8;
  localparam int HALF = 3;  // clk cycles per sclk phase

  logic clk = 0;
  logic rst_n;
  logic csr_mode, csr_sclk, csr_mosi;
  logic psel, penable, pwrite;
  logic [ADDR_W-1:0] paddr;
  logic [DATA_W-1:0] pwdata, prdata;
  logic pready;
  logic [DATA_W-1:0] rdata_out;
  logic read_valid, loopback_en;
  logic tx_full = 0, tx_empty = 0, rx_empty = 0, rx_error = 0;

  always #10 clk = ~clk;

  csr_pin_adapter #(
      .ADDR_W(ADDR_W),
      .DATA_W(DATA_W)
  ) u_ad (
      .clk(clk), .rst_n(rst_n), .csr_mode(csr_mode), .csr_sclk(csr_sclk),
      .csr_mosi(csr_mosi), .psel(psel), .penable(penable), .pwrite(pwrite),
      .paddr(paddr), .pwdata(pwdata), .prdata(prdata), .pready(pready),
      .rdata_out(rdata_out), .read_valid(read_valid)
  );

  apb_csr #(
      .ADDR_W(ADDR_W),
      .DATA_W(DATA_W)
  ) u_cs (
      .clk(clk), .rst_n(rst_n), .psel(psel), .penable(penable), .pwrite(pwrite),
      .paddr(paddr), .pwdata(pwdata), .prdata(prdata), .pready(pready),
      .loopback_en(loopback_en), .parity_en(), .parity_odd(), .baud_div(),
      .tx_full(tx_full), .tx_empty(tx_empty), .rx_empty(rx_empty), .rx_error(rx_error), .rx_overflow(1'b0)
  );

  integer f, i;
  logic [11:0] frame = 12'b1_000_0000_0001;  // rw=1, addr=CTRL(0), data=0x01

  // Negedge stimulus, no posedge race
  task shift_bit(input logic b);
    begin
      @(negedge clk);
      csr_mosi = b;
      repeat (HALF) @(negedge clk);
      csr_sclk = 1;
      repeat (HALF) @(negedge clk);
      csr_sclk = 0;
    end
  endtask

  initial begin
    f = $fopen("uart_csr_wave.csv", "w");
    $fwrite(f, "csr_mode,csr_sclk,csr_mosi,psel,penable,pwrite,paddr,pwdata,loopback_en\n");
    csr_mode = 0; csr_sclk = 0; csr_mosi = 0; rst_n = 0;
    repeat (3) @(posedge clk);
    rst_n = 1;
    repeat (2) @(posedge clk);
    csr_mode = 1;
    repeat (2) @(posedge clk);
    for (i = 11; i >= 0; i = i - 1) shift_bit(frame[i]);
    repeat (10) @(posedge clk);
    csr_mode = 0;
    repeat (2) @(posedge clk);
    $fclose(f);
    $finish;
  end

  always @(posedge clk)
    if (rst_n)
      $fwrite(f, "%b,%b,%b,%b,%b,%b,%0d,%0d,%b\n",
              csr_mode, csr_sclk, csr_mosi, psel, penable, pwrite, paddr, pwdata, loopback_en);

endmodule
