// Generates uart_wave.csv for the README loopback waveform (Throwaway)
//   iverilog -g2012 -s uart_wave_tb -o w.vvp -I src src/project.sv src/uart.sv \
//     src/uart_tx.sv src/uart_rx.sv src/tick_gen.sv src/synchronizer.sv src/sync_fifo.sv docs/uart_wave_tb.sv
//   vvp w.vvp && python3 docs/uart_waveform.py
`default_nettype none

module uart_wave_tb;
  reg clk = 0;
  reg rst_n, ena;
  reg [7:0] ui_in, uio_in;
  wire [7:0] uo_out, uio_out, uio_oe;
  integer f, i;

  tt_um_drewbabel_uart dut (
      .ui_in(ui_in),
      .uo_out(uo_out),
      .uio_in(uio_in),
      .uio_out(uio_out),
      .uio_oe(uio_oe),
      .ena(ena),
      .clk(clk),
      .rst_n(rst_n)
  );

  always #10 clk = ~clk;  // 50 MHz

  task dump;
    $fwrite(f, "%b,%b,%b,%0d\n", uio_out[3], uio_out[5], uio_out[6], uo_out);
  endtask

  initial begin
    f = $fopen("uart_wave.csv", "w");
    $fwrite(f, "tx_serial,rx_empty,rx_error,uo_out\n");
    ena = 1;
    ui_in = 0;
    uio_in = 8'b0000_0001;
    rst_n = 0;
    repeat (20) @(posedge clk);
    rst_n = 1;
    @(posedge clk);

    // push 0x5A into the TX FIFO
    ui_in = 8'h5A;
    uio_in[1] = 1;
    @(posedge clk);
    uio_in[1] = 0;
    ui_in = 0;

    // loop tx_serial -> rx_serial, dump each clock until a byte lands
    for (i = 0; i < 6000; i = i + 1) begin
      uio_in[0] = uio_out[3];
      dump;
      @(posedge clk);
      if (uio_out[5] == 0) i = 6000;
    end

    // tail: hold the received state, pop mid-window so uo_out shows the byte
    for (i = 0; i < 500; i = i + 1) begin
      uio_in[0] = uio_out[3];
      uio_in[2] = (i == 150);  // one-cycle rx_pop pulse
      dump;
      @(posedge clk);
    end

    $fclose(f);
    $finish;
  end
endmodule
