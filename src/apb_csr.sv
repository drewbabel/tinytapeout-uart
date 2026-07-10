module apb_csr #(
    parameter int ADDR_W = 3,
    parameter int DATA_W = 8
) (
    input logic clk,
    input logic rst_n,

    input  logic              psel,
    input  logic              penable,
    input  logic              pwrite,
    input  logic [ADDR_W-1:0] paddr,
    input  logic [DATA_W-1:0] pwdata,
    output logic [DATA_W-1:0] prdata,
    output logic              pready,

    output logic                loopback_en,
    output logic                parity_en,
    output logic                parity_odd,
    output logic [2*DATA_W-1:0] baud_div,

    input logic tx_full,
    input logic tx_empty,
    input logic rx_empty,
    input logic rx_error,
    input logic rx_overflow
);

  localparam logic [ADDR_W-1:0] RegCtrl = 3'd0;
  localparam logic [ADDR_W-1:0] RegStatus = 3'd1;
  localparam logic [ADDR_W-1:0] RegScratch = 3'd2;
  localparam logic [ADDR_W-1:0] RegBaudLo = 3'd3;
  localparam logic [ADDR_W-1:0] RegBaudHi = 3'd4;

  logic [DATA_W-1:0] ctrl_reg;
  logic [DATA_W-1:0] scratch_reg;
  logic [DATA_W-1:0] baud_lo_reg;
  logic [DATA_W-1:0] baud_hi_reg;
  logic apb_access;

  // Sticky until a CTRL write clears them
  logic err_sticky;
  logic ovf_sticky;

  assign apb_access = (psel && penable);
  assign pready = 1'b1;
  assign loopback_en = ctrl_reg[0];
  assign parity_en = ctrl_reg[1];
  assign parity_odd = ctrl_reg[2];
  assign baud_div = {baud_hi_reg, baud_lo_reg};

  always_ff @(posedge clk) begin
    if (!rst_n) begin
      ctrl_reg <= '0;
      scratch_reg <= '0;
      baud_lo_reg <= '0;
      baud_hi_reg <= '0;
      err_sticky <= 1'b0;
      ovf_sticky <= 1'b0;
    end else begin
      if (rx_error) err_sticky <= 1'b1;
      if (rx_overflow) ovf_sticky <= 1'b1;
      if (apb_access && pwrite) begin
        case (paddr)
          RegCtrl: begin
            ctrl_reg   <= pwdata;
            err_sticky <= 1'b0;
            ovf_sticky <= 1'b0;
          end
          RegScratch: scratch_reg <= pwdata;
          RegBaudLo:  baud_lo_reg <= pwdata;
          RegBaudHi:  baud_hi_reg <= pwdata;
          default:    ;
        endcase
      end
    end
  end

  always_comb begin
    case (paddr)
      RegCtrl:    prdata = ctrl_reg;
      RegStatus:  prdata = {3'b0, ovf_sticky, err_sticky, rx_empty, tx_empty, tx_full};
      RegScratch: prdata = scratch_reg;
      RegBaudLo:  prdata = baud_lo_reg;
      RegBaudHi:  prdata = baud_hi_reg;
      default:    prdata = '0;
    endcase
  end

endmodule
