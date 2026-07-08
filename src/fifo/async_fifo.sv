module async_fifo #(
    parameter int WIDTH = 8,
    parameter int DEPTH = 16,
    localparam int AW = $clog2(DEPTH)
) (
    // Write
    input  logic             wr_clk,
    input  logic             wr_rst_n,
    input  logic             wr_en,
    input  logic [WIDTH-1:0] wr_data,
    output logic             full,

    // Read
    input  logic             rd_clk,
    input  logic             rd_rst_n,
    input  logic             rd_en,
    output logic [WIDTH-1:0] rd_data,
    output logic             empty
);

  logic [  AW:0] wr_gray;
  logic [  AW:0] rd_gray;
  logic [  AW:0] wr_gray_sync;
  logic [  AW:0] rd_gray_sync;
  logic [AW-1:0] wr_addr;
  logic [AW-1:0] rd_addr;

`ifdef FORMAL
  logic [AW:0] wr_gray_mid;  // wr sync stage-1
  logic [AW:0] rd_gray_mid;  // rd sync stage-1
`endif

  // Synchronizer for write pointer to read clock domain
  synchronizer #(
      .WIDTH(AW + 1)
  ) u_rd_gray_sync (
      .clk(wr_clk),
      .rst_n(wr_rst_n),
      .d(rd_gray),
      .q(rd_gray_sync)
`ifdef FORMAL,
      .mid(rd_gray_mid)
`endif
  );

  // Synchronizer for read pointer to write clock domain
  synchronizer #(
      .WIDTH(AW + 1)
  ) u_wr_gray_sync (
      .clk(rd_clk),
      .rst_n(rd_rst_n),
      .d(wr_gray),
      .q(wr_gray_sync)
`ifdef FORMAL,
      .mid(wr_gray_mid)
`endif
  );

  // Write pointer and full flag
  wptr_full #(
      .DEPTH(DEPTH)
  ) u_wptr_full (
      .wr_clk(wr_clk),
      .wr_rst_n(wr_rst_n),
      .wr_en(wr_en),
      .rd_gray_sync(rd_gray_sync),
      .full(full),
      .wr_addr(wr_addr),
      .wr_gray(wr_gray)
  );

  // Read pointer and empty flag
  rptr_empty #(
      .DEPTH(DEPTH)
  ) u_rptr_empty (
      .rd_clk(rd_clk),
      .rd_rst_n(rd_rst_n),
      .rd_en(rd_en),
      .wr_gray_sync(wr_gray_sync),
      .empty(empty),
      .rd_addr(rd_addr),
      .rd_gray(rd_gray)
  );

  // FIFO memory
  fifomem #(
      .WIDTH(WIDTH),
      .DEPTH(DEPTH)
  ) u_fifomem (
      .wr_clk(wr_clk),
      .wr_en(wr_en),
      .full(full),
      .wr_addr(wr_addr),
      .wr_data(wr_data),
      .rd_clk(rd_clk),
      .rd_en(rd_en),
      .empty(empty),
      .rd_addr(rd_addr),
      .rd_data(rd_data)
  );

`ifdef FORMAL
  logic [AW:0] occupancy;
  logic [AW:0] wptr = gray2bin(wr_gray);  // True write
  logic [AW:0] rptr = gray2bin(rd_gray);  // True read
  logic [AW:0] wptr_rd = gray2bin(wr_gray_sync);  // Write seen by read domain
  logic [AW:0] rptr_wr = gray2bin(rd_gray_sync);  // Read seen by write domain

  function automatic logic [AW:0] gray2bin(input logic [AW:0] g);
    for (int i = 0; i <= AW; i++) gray2bin[i] = ^(g >> i);
  endfunction

  assign occupancy = wptr - rptr;

  // Pointer views as offsets from the furthest behind pointer: rptr_wr
  logic [AW:0] o_rdmid, o_rptr, o_wrrd, o_wrmid, o_wptr;
  assign o_rdmid = gray2bin(rd_gray_mid) - rptr_wr;
  assign o_rptr  = rptr - rptr_wr;
  assign o_wrrd  = wptr_rd - rptr_wr;
  assign o_wrmid = gray2bin(wr_gray_mid) - rptr_wr;
  assign o_wptr  = wptr - rptr_wr;

  // Flops start at 0 (submodule initial-assumes), no reset
  always_comb begin
    assume (wr_rst_n);
    assume (rd_rst_n);

    // Ring order
    assert (o_rdmid <= o_rptr);
    assert (o_rptr <= o_wrrd);
    assert (o_wrrd <= o_wrmid);
    assert (o_wrmid <= o_wptr);
    assert (o_wptr <= DEPTH);

    // Safety
    assert (occupancy <= DEPTH);
    if (occupancy == 0) assert (empty);
    if (occupancy == DEPTH) assert (full);
  end

  always @(posedge wr_clk) cover (full == 1'b1);
  always @(posedge rd_clk) cover (empty == 1'b1);

`endif

endmodule
