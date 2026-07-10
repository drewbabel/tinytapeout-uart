module uart_rx #(
    parameter int CLK_FREQ_HZ = 100_000_000,
    parameter int BAUD_RATE   = 115_200,
    parameter int OVERSAMPLE  = 16,
    parameter int DATA_BITS   = 8,
    parameter int BaudW       = 16
) (
    input logic clk,
    input logic rst_n,
    input logic rx_serial,
    input logic parity_en,
    input logic parity_odd,
    input logic [BaudW-1:0] baud_div,
    output logic [DATA_BITS-1:0] rx_data,
    output logic rx_valid,
    output logic rx_error
);

  // (A+B/2)/B ensures correctly rounded
  localparam int ClksPerBit = (CLK_FREQ_HZ + BAUD_RATE / 2) / BAUD_RATE;
  localparam int ClksPerOversample = (ClksPerBit + OVERSAMPLE / 2) / OVERSAMPLE;

  typedef enum logic [1:0] {
    IDLE,
    START,
    DATA,
    RESULT
  } state_t;

  state_t state, next_state;
  logic in;
  logic in_prev;
  logic tick;
  logic tick_clr;
  logic [$clog2(OVERSAMPLE)-1:0] tick_cnt;
  logic [$clog2(DATA_BITS):0] data_cnt;
  logic par_rx;
  logic exp_par;
  logic par_bad;
  logic [BaudW-1:0] rx_os_div;

  assign rx_os_div = baud_div >> $clog2(OVERSAMPLE);
  assign par_bad   = parity_en && (par_rx != exp_par);

  synchronizer #(
      .WIDTH(1)
  ) sync_FF (
      .clk  (clk),
      .rst_n(rst_n),
      .d    (rx_serial),
      .q    (in)
  );

  tick_gen #(
      .DIVISOR(ClksPerOversample),
      .Width  (BaudW)
  ) oversample_tick (
      .clk    (clk),
      .rst_n  (rst_n),
      .clr    (tick_clr),
      .divisor(rx_os_div),
      .tick   (tick)
  );

  parity #(
      .DATA_BITS(DATA_BITS)
  ) u_par (
      .data(rx_data),
      .odd (parity_odd),
      .p   (exp_par)
  );

  always_ff @(posedge clk) begin
    rx_valid <= 1'b0;
    rx_error <= 1'b0;
    if (!rst_n) begin
      state <= IDLE;
      tick_cnt <= '0;
      data_cnt <= '0;
      in_prev <= 1'b0;
      rx_data <= '0;
      par_rx <= 1'b0;
    end else begin
      state   <= next_state;
      in_prev <= in;

      // Result Pulse
      if (state == RESULT && next_state == IDLE) begin
        rx_valid <= in && !par_bad;
        rx_error <= !in || par_bad;
      end

      // Counter logic
      if (tick) begin
        if (tick_cnt == $bits(tick_cnt)'(OVERSAMPLE - 1)) begin
          tick_cnt <= '0;

          // Bit boundary
          case (state)
            DATA: begin
              data_cnt <= data_cnt + 1'b1;
              if (data_cnt < $bits(data_cnt)'(DATA_BITS)) rx_data <= {in, rx_data[DATA_BITS-1:1]};
              else par_rx <= in;
            end
            default: data_cnt <= '0;
          endcase
        end else tick_cnt <= tick_cnt + 1'b1;
      end

      if (tick_clr) begin
        tick_cnt <= '0;
        data_cnt <= '0;
      end
    end
  end

  always_comb begin
    tick_clr   = 1'b0;
    next_state = state;

    case (state)
      IDLE: begin
        if (in_prev && !in) begin
          next_state = START;
          tick_clr   = 1'b1;
        end
      end

      START: begin
        if (!in) begin
          if (tick_cnt == $bits(tick_cnt)'(OVERSAMPLE / 2)) begin
            next_state = DATA;
            tick_clr   = 1'b1;
          end
        end else next_state = IDLE;
      end

      DATA: begin
        if (!parity_en && data_cnt == $bits(data_cnt)'(DATA_BITS)) begin
          next_state = RESULT;
          tick_clr   = 1'b1;
        end else if (parity_en && data_cnt == $bits(data_cnt)'(DATA_BITS + 1)) begin
          next_state = RESULT;
          tick_clr   = 1'b1;
        end
      end

      RESULT: begin
        if (tick_cnt == $bits(tick_cnt)'(OVERSAMPLE - 1)) begin
          next_state = IDLE;
        end
      end

      default: next_state = IDLE;
    endcase
  end

`ifdef FORMAL
  logic f_past_valid = 0;
  initial assume (!rst_n);
  initial assume (state == IDLE);
  initial assume (!(rx_valid && rx_error));

  always @(posedge clk) begin
    f_past_valid <= 1'b1;
    cover (state == START);  // Ensure reachable in a few cycles

    // $past has no valid history on cycle 0 (use f_past_valid register)
    if (f_past_valid) begin
      assert (!(rx_valid && $past(rx_valid)));
      assert (!(rx_error && $past(rx_error)));

      assert (!(!$past(rst_n) && rx_valid));
      assert (!(!$past(rst_n) && rx_error));
    end

    assert (!(rx_valid && rx_error));
  end
`endif

endmodule
