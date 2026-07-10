module uart_tx #(
    parameter int CLK_FREQ_HZ = 100_000_000,
    parameter int BAUD_RATE   = 115_200,
    parameter int DATA_BITS   = 8,
    parameter int BaudW       = 16
) (
    input logic clk,
    input logic rst_n,
    input logic [DATA_BITS-1:0] tx_data,
    input logic tx_valid,
    input logic parity_en,
    input logic parity_odd,
    input logic [BaudW-1:0] baud_div,
    output logic tx_ready,
    output logic tx_serial
);

  localparam int ClksPerBit = (CLK_FREQ_HZ + BAUD_RATE / 2) / BAUD_RATE;

  typedef enum logic [2:0] {
    IDLE,
    START,
    DATA,
    PARITY,
    STOP
  } state_t;

  state_t state, next_state;
  logic tick;
  logic tick_clr;
  logic [DATA_BITS-1:0] data;
  logic [$clog2(DATA_BITS):0] data_cnt;
  logic tx_par;
  logic par_bit;

  // Config latched per frame
  logic par_en_q;
  logic [BaudW-1:0] baud_q;

  parity #(
      .DATA_BITS(DATA_BITS)
  ) u_par (
      .data(tx_data),
      .odd (parity_odd),
      .p   (par_bit)
  );

  tick_gen #(
      .DIVISOR(ClksPerBit),
      .Width  (BaudW)
  ) oversample_tick (
      .clk    (clk),
      .rst_n  (rst_n),
      .clr    (tick_clr),
      .divisor(baud_q),
      .tick   (tick)
  );

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      state <= IDLE;
      tx_serial <= 1'b1;
      data_cnt <= '0;
      data <= '0;
      tx_par <= 1'b0;
      par_en_q <= 1'b0;
      baud_q <= '0;
    end else begin
      state <= next_state;
      if (tx_valid && tx_ready) begin
        data     <= tx_data;
        tx_par   <= par_bit;
        par_en_q <= parity_en;
        baud_q   <= baud_div;
      end

      case (state)
        START: begin
          tx_serial <= 1'b0;
          data_cnt  <= '0;
        end

        DATA: begin
          tx_serial <= data[0];
          if (tick) begin
            data <= data >> 1;
            data_cnt <= data_cnt + 1'b1;
          end
        end

        PARITY: begin
          tx_serial <= tx_par;
        end

        STOP: begin
          tx_serial <= 1'b1;
        end
        default: data_cnt <= '0;
      endcase
    end
  end

  always_comb begin
    next_state = state;
    tx_ready   = 1'b0;

    case (state)
      IDLE: begin
        if (rst_n) tx_ready = 1'b1;
        if (tx_valid && tx_ready) begin
          next_state = START;
        end
      end

      START: begin
        if (tick) begin
          next_state = DATA;
        end
      end

      DATA: begin
        if (data_cnt == $bits(data_cnt)'(DATA_BITS - 1)) begin
          if (tick) begin
            if (par_en_q) next_state = PARITY;
            else next_state = STOP;
          end
        end
      end

      PARITY: begin
        if (tick) next_state = STOP;
      end

      STOP: begin
        if (tick) begin
          tx_ready = 1'b1;
          if (tx_valid) next_state = START;
          else next_state = IDLE;
        end

      end

      default: next_state = IDLE;
    endcase

    if (!rst_n) tx_ready = 1'b0;
    tick_clr = (state != next_state) ? 1'b1 : 1'b0;
  end

`ifdef FORMAL
  logic f_past_valid = 0;
  initial assume (!rst_n);
  initial assume (tx_serial);
  initial assume (state == IDLE);

  always @(posedge clk) begin
    f_past_valid <= 1'b1;
    cover (state == START);  // Ensure reachable in a few cycles

    assert (!((state == START || state == DATA) && tx_ready));
    assert (!(state == IDLE) || tx_serial);

    assert (rst_n || !tx_ready);
    if (f_past_valid) begin  // $past has no valid history on cycle 0 (use f_past_valid register)
      assert ($past(rst_n) || tx_serial);
    end
  end
`endif

endmodule
