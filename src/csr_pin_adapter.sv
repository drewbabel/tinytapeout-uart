module csr_pin_adapter #(
    parameter int ADDR_W = 3,
    parameter int DATA_W = 8
) (
    input logic clk,
    input logic rst_n,

    // 2FF-synced by the parent
    input logic csr_mode,
    input logic csr_sclk,
    input logic csr_mosi,

    output logic              psel,
    output logic              penable,
    output logic              pwrite,
    output logic [ADDR_W-1:0] paddr,
    output logic [DATA_W-1:0] pwdata,
    input  logic [DATA_W-1:0] prdata,
    input  logic              pready,

    output logic [DATA_W-1:0] rdata_out,
    output logic              read_valid
);

  // Frame = { rw, addr[2:0], data[7:0] }, 12 bits, MSB first
  localparam int FrameBits = 1 + ADDR_W + DATA_W;

  logic mode_sync;
  logic sclk_sync;
  logic mosi_sync;
  assign mode_sync = csr_mode;
  assign sclk_sync = csr_sclk;
  assign mosi_sync = csr_mosi;

  logic sclk_sync_d;
  logic sclk_rise;
  always_ff @(posedge clk) begin
    if (!rst_n) sclk_sync_d <= 1'b0;
    else sclk_sync_d <= sclk_sync;
  end
  assign sclk_rise = sclk_sync & ~sclk_sync_d;

  logic [FrameBits-1:0] frame_sr;
  logic [$clog2(FrameBits+1)-1:0] bit_cnt;
  logic frame_valid;

  always_ff @(posedge clk) begin
    if (!rst_n || !mode_sync) begin
      frame_sr    <= '0;
      bit_cnt     <= '0;
      frame_valid <= 1'b0;
    end else begin
      frame_valid <= 1'b0;
      if (sclk_rise) begin
        frame_sr <= {frame_sr[FrameBits-2:0], mosi_sync};
        if (bit_cnt == $bits(bit_cnt)'(FrameBits - 1)) begin
          bit_cnt     <= '0;
          frame_valid <= 1'b1;
        end else bit_cnt <= bit_cnt + 1'b1;
      end
    end
  end

  logic              frame_rw;
  logic [ADDR_W-1:0] frame_addr;
  logic [DATA_W-1:0] frame_data;
  assign frame_rw   = frame_sr[FrameBits-1];
  assign frame_addr = frame_sr[FrameBits-2-:ADDR_W];
  assign frame_data = frame_sr[DATA_W-1:0];

  typedef enum logic [1:0] {
    IDLE,
    SETUP,
    ACCESS
  } state_t;
  state_t state, next_state;

  assign pwrite = frame_rw;
  assign paddr  = frame_addr;
  assign pwdata = frame_data;

  assign psel    = (state != IDLE);
  assign penable = (state == ACCESS);

  always_comb begin
    next_state = state;
    case (state)
      IDLE:    if (frame_valid) next_state = SETUP;
      SETUP:   next_state = ACCESS;
      ACCESS:  if (pready) next_state = IDLE;
      default: next_state = IDLE;
    endcase
  end

  always_ff @(posedge clk) begin
    if (!rst_n || !mode_sync) begin
      state      <= IDLE;
      rdata_out  <= '0;
      read_valid <= 1'b0;
    end else begin
      state <= next_state;
      // Hold rdata until csr_mode drops or the next frame starts
      if (state == ACCESS && pready && !frame_rw) begin
        rdata_out  <= prdata;
        read_valid <= 1'b1;
      end else if (sclk_rise && bit_cnt == '0) begin
        read_valid <= 1'b0;
      end
    end
  end

endmodule
