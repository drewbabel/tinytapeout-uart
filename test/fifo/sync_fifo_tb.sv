module sync_fifo_tb ();

  int checks = 0;
  int errors = 0;

  localparam int Width = 8;
  localparam int Depth = 16;

  logic clk = 1'b0;
  logic rst_n = 1'b1;
  logic wr_en = 1'b0;
  logic rd_en = 1'b0;
  logic [Width-1:0] wr_data;
  logic [Width-1:0] rd_data;
  logic full;
  logic empty;

  logic [Width-1:0] byte_q[$];
  logic exp_full;
  logic exp_empty;

  sync_fifo #(
      .WIDTH(Width),
      .DEPTH(Depth)
  ) dut (
      .clk(clk),
      .rst_n(rst_n),
      .wr_en(wr_en),
      .rd_en(rd_en),
      .wr_data(wr_data),
      .rd_data(rd_data),
      .full(full),
      .empty(empty)
  );

  always #5 clk = ~clk;

  task automatic do_reset();
    rst_n  = 1'b0;
    byte_q = {};
    @(posedge clk);
    #1 rst_n = 1'b1;
    @(posedge clk);
  endtask  // Automatic

  task automatic do_verdict();
    @(posedge clk);
    if (errors == 0) begin
      $display("PASS: %0d checks, %0d mismatches", checks, errors);
    end else begin
      $fatal(1, "FAIL: %0d mismatches, %0d checks", errors, checks);
    end
    $finish;
  endtask  // Automatic

  task automatic check_size();
    checks++;
    if (empty !== exp_empty) begin
      errors++;
      $error("t=%0t empty mismatch: got=%b exp=%b", $time, empty, exp_empty);
    end

    checks++;
    if (full !== exp_full) begin
      errors++;
      $error("t=%0t full mismatch: got=%b exp=%b", $time, full, exp_full);
    end
  endtask  // Automatic

  task automatic write_data(input logic [Width-1:0] data);
    wr_data = data;
    #1 wr_en = 1'b1;
    if (byte_q.size() < Depth) byte_q.push_back(data);
    @(posedge clk);
    #1 wr_en = 1'b0;
  endtask  // Automatic

  task automatic read_data();
    logic [Width-1:0] got;
    logic [Width-1:0] exp;
    logic did_read;

    did_read = (byte_q.size() > 0);
    #1 rd_en = 1'b1;
    if (did_read) exp = byte_q.pop_front();
    @(posedge clk);
    #1 got = rd_data;
    #1 rd_en = 1'b0;
    if (did_read) begin
      checks++;
      if (got !== exp) begin
        errors++;
        $error("t=%0t data mismatch: got=%b exp=%b", $time, got, exp);
      end
    end
  endtask  // Automatic

  initial begin
    $dumpfile("tb.vcd");
    $dumpvars(0, sync_fifo_tb);
    do_reset();

    // Check full blocks writes, empty blocks reads
    repeat (Depth + 5) write_data((Width)'($urandom));
    repeat (Depth + 5) read_data();

    // Wrap pointers
    repeat (3 * Depth) begin
      write_data((Width)'($urandom));
      read_data();
    end

    // Ensure write/read blocking still works
    repeat (Depth + 5) write_data((Width)'($urandom));
    repeat (Depth + 5) read_data();

    do_verdict();
  end

  // Watchdog
  initial begin
    #200_000_000 $fatal(1, "TIMEOUT: sim exceeded max time");
  end

  // Reference model
  always @(posedge clk) begin
    exp_empty = (byte_q.size() == 0);
    exp_full  = (byte_q.size() == Depth);
  end

  always @(negedge clk) begin
    check_size();
  end

endmodule
