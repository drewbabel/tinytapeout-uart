`default_nettype none

module basys3_top (
    input  logic        clk,
    input  logic        btnc,
    input  logic        btnu,
    input  logic        btnd,
    input  logic [ 7:0] sw,
    input  logic        serial_rx,
    output logic        serial_tx,
    output logic [15:0] led
);

  logic [7:0] uo_out;
  logic [7:0] uio_out;
  logic [7:0] uio_oe;

  tt_um_drewbabel_uart tile (
      .ui_in  (sw),
      .uo_out (uo_out),
      .uio_in ({4'b0000, 1'b0, btnd, btnu, serial_rx}),
      .uio_out(uio_out),
      .uio_oe (uio_oe),
      .ena    (1'b1),
      .clk    (clk),
      .rst_n  (~btnc)
  );

  assign serial_tx = uio_out[3];
  assign led = {uio_out[6], uio_out[5], uio_out[4], 5'b0, uo_out};

  logic _unused;
  assign _unused = &{uio_oe, uio_out[7], uio_out[2:0], 1'b0};

endmodule
