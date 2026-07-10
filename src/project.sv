`default_nettype none

module tt_um_drewbabel_uart (
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);

  logic csr_mode;
  logic csr_sclk;
  logic csr_mosi;
  assign csr_mode = uio_in[7];
  assign csr_sclk = uio_in[1];
  assign csr_mosi = ui_in[0];

  // Host strobes, gated off in CSR mode
  logic rx_pop;
  logic tx_push;
  assign tx_push = uio_in[1] & ~csr_mode;
  assign rx_pop  = uio_in[2] & ~csr_mode;

  logic [7:0] tx_fifo_dout;
  logic       tx_full;
  logic       tx_empty;
  logic       tx_fifo_rd;

  sync_fifo #(
      .WIDTH(8),
      .DEPTH(16)
  ) tx_fifo (
      .clk    (clk),
      .rst_n  (rst_n),
      .wr_en  (tx_push),
      .rd_en  (tx_fifo_rd),
      .wr_data(ui_in),
      .rd_data(tx_fifo_dout),
      .full   (tx_full),
      .empty  (tx_empty)
  );

  logic       uart_tx_ready;
  logic       uart_tx_serial;
  logic       uart_tx_valid;
  logic [7:0] uart_rx_data;
  logic       uart_rx_valid;
  logic       uart_rx_error;

  logic       loopback_en;
  logic       rx_serial;
  assign rx_serial = loopback_en ? uart_tx_serial : uio_in[0];

  logic        parity_en;
  logic        parity_odd;
  logic [15:0] baud_div;

  uart #(
      .CLK_FREQ_HZ(50_000_000),  // FINALIZE at submission: match the TT clock you request
      .BAUD_RATE  (115_200),
      .OVERSAMPLE (16),
      .DATA_BITS  (8),
      .BaudW      (16)
  ) u_uart (
      .clk       (clk),
      .rst_n     (rst_n),
      .parity_en (parity_en),
      .parity_odd(parity_odd),
      .baud_div  (baud_div),
      .tx_data   (tx_fifo_dout),
      .tx_valid  (uart_tx_valid),
      .tx_ready  (uart_tx_ready),
      .tx_serial (uart_tx_serial),
      .rx_serial (rx_serial),
      .rx_data   (uart_rx_data),
      .rx_valid  (uart_rx_valid),
      .rx_error  (uart_rx_error)
  );

  localparam logic [1:0] TIdle = 2'd0, TRead = 2'd1, TSend = 2'd2;
  logic [1:0] tstate;

  always_comb begin
    tx_fifo_rd    = (tstate == TRead);
    uart_tx_valid = (tstate == TSend);
  end

  always @(posedge clk) begin
    if (!rst_n) tstate <= TIdle;
    else begin
      case (tstate)
        TIdle:   if (!tx_empty && uart_tx_ready) tstate <= TRead;
        TRead:   tstate <= TSend;
        TSend:   tstate <= TIdle;
        default: tstate <= TIdle;
      endcase
    end
  end

  logic [7:0] rx_fifo_dout;
  logic       rx_empty;
  logic       rx_full_unused;

  sync_fifo #(
      .WIDTH(8),
      .DEPTH(16)
  ) rx_fifo (
      .clk    (clk),
      .rst_n  (rst_n),
      .wr_en  (uart_rx_valid),
      .rd_en  (rx_pop),
      .wr_data(uart_rx_data),
      .rd_data(rx_fifo_dout),
      .full   (rx_full_unused),
      .empty  (rx_empty)
  );

  localparam int CsrAddrW = 3;
  localparam int CsrDataW = 8;

  logic                csr_psel;
  logic                csr_penable;
  logic                csr_pwrite;
  logic [CsrAddrW-1:0] csr_paddr;
  logic [CsrDataW-1:0] csr_pwdata;
  logic [CsrDataW-1:0] csr_prdata;
  logic                csr_pready;
  logic [CsrDataW-1:0] csr_rdata_out;
  logic                csr_read_valid;

  csr_pin_adapter #(
      .ADDR_W(CsrAddrW),
      .DATA_W(CsrDataW)
  ) u_csr_adapter (
      .clk       (clk),
      .rst_n     (rst_n),
      .csr_mode  (csr_mode),
      .csr_sclk  (csr_sclk),
      .csr_mosi  (csr_mosi),
      .psel      (csr_psel),
      .penable   (csr_penable),
      .pwrite    (csr_pwrite),
      .paddr     (csr_paddr),
      .pwdata    (csr_pwdata),
      .prdata    (csr_prdata),
      .pready    (csr_pready),
      .rdata_out (csr_rdata_out),
      .read_valid(csr_read_valid)
  );

  apb_csr #(
      .ADDR_W(CsrAddrW),
      .DATA_W(CsrDataW)
  ) u_csr (
      .clk        (clk),
      .rst_n      (rst_n),
      .psel       (csr_psel),
      .penable    (csr_penable),
      .pwrite     (csr_pwrite),
      .paddr      (csr_paddr),
      .pwdata     (csr_pwdata),
      .prdata     (csr_prdata),
      .pready     (csr_pready),
      .loopback_en(loopback_en),
      .parity_en  (parity_en),
      .parity_odd (parity_odd),
      .baud_div   (baud_div),
      .tx_full    (tx_full),
      .tx_empty   (tx_empty),
      .rx_empty   (rx_empty),
      .rx_error   (uart_rx_error)
  );

  assign uo_out     = csr_read_valid ? csr_rdata_out : rx_fifo_dout;
  assign uio_out[0] = 1'b0;
  assign uio_out[1] = 1'b0;
  assign uio_out[2] = 1'b0;
  assign uio_out[3] = uart_tx_serial;
  assign uio_out[4] = tx_full;
  assign uio_out[5] = rx_empty;
  assign uio_out[6] = uart_rx_error;
  assign uio_out[7] = 1'b0;
  assign uio_oe     = 8'b0111_1000;  // 1 = output: pins 3,4,5,6

  logic _unused;
  assign _unused = &{ena, uio_in[6:3], rx_full_unused, 1'b0};

endmodule
