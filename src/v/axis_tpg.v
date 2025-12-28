`timescale 1ns/1ps

module axis_tpg #(
    parameter WIDTH = 256,           // Image width
    parameter HEIGHT = 256,          // Image height
    parameter DATA_WIDTH = 24,        // Pixel data width (e.g., 24 for RGB888)
    parameter sel_i_WIDTH = 3   // Pattern selection width
) (
    input  wire                        clk_i,
    input  wire                        rstn_i,
    input  wire                        en_i,
    input  wire [sel_i_WIDTH-1:0]      sel_i,

    // AXI Stream Master Interface
    output reg                         m_axis_tvalid_o,
    input  wire                        m_axis_tready_i,
    output reg  [DATA_WIDTH-1:0]       m_axis_tdata_o,
    output reg                         m_axis_tlast_o,
    output reg                         m_axis_tuser_o    // Start of frame
);

    /* verilator lint_off WIDTHTRUNC */
    /* verilator lint_off WIDTHEXPAND */

    // Pattern selection constants
    localparam PATTERN_SOLID      = 3'd0;
    localparam PATTERN_COLORBAR   = 3'd1;
    localparam PATTERN_HGRADIENT  = 3'd2;
    localparam PATTERN_VGRADIENT  = 3'd3;
    localparam PATTERN_CHECKERBRD = 3'd4;
    localparam PATTERN_RAMP       = 3'd5;

    // Coordinates
    reg [$clog2(WIDTH)-1:0]  px_cnt;
    reg [$clog2(HEIGHT)-1:0] row_cnt;

    // State machine
    localparam IDLE = 1'b0;
    localparam ACTIVE = 1'b1;
    reg state;

    wire m_axis_transfer_ok = m_axis_tvalid_o && m_axis_tready_i;

    wire last_pixel = (px_cnt == WIDTH-1) && (row_cnt == HEIGHT-1);

    wire eol = (px_cnt == WIDTH-1);

    // Pattern generation wires
    wire [DATA_WIDTH-1:0] pattern_data;

    // State machine
    always @(posedge clk_i, negedge rstn_i) begin
        if (!rstn_i) begin
            state <= IDLE;
        end else begin
            case (state)
                IDLE: begin
                    if (en_i) begin
                        state <= ACTIVE;
                    end
                end
                ACTIVE: begin
                    if (!en_i || (m_axis_transfer_ok && last_pixel)) begin
                        state <= IDLE;
                    end
                end
            endcase
        end
    end

    // Coordinate counters
    always @(posedge clk_i, negedge rstn_i) begin
        if (!rstn_i) begin
            px_cnt <= 0;
            row_cnt <= 0;
        end else begin
            if (state == IDLE) begin
                px_cnt <= 0;
                row_cnt <= 0;
            end else if (m_axis_transfer_ok) begin
                if (eol) begin
                    px_cnt <= 0;
                    if (last_pixel) begin
                        row_cnt <= 0;
                    end else begin
                        row_cnt <= row_cnt + 1;
                    end
                end else begin
                    px_cnt <= px_cnt + 1;
                end
            end
        end
    end

    // AXI Stream output control
    always @(posedge clk_i, negedge rstn_i) begin
        if (!rstn_i) begin
            m_axis_tvalid_o <= 1'b0;
            m_axis_tdata_o  <= 0;
            m_axis_tlast_o  <= 1'b0;
            m_axis_tuser_o  <= 1'b0;
        end else begin
            case (state)
                IDLE: begin
                    m_axis_tvalid_o <= 1'b0;
                    m_axis_tlast_o  <= 1'b0;
                    m_axis_tuser_o  <= 1'b0;
                    m_axis_tdata_o  <= 0; // output won't matter for IDLE case, set to 0 for low power
                end
                ACTIVE: begin
                    m_axis_tvalid_o <= 1'b1;
                    m_axis_tdata_o  <= pattern_data;
                    m_axis_tlast_o  <= eol;
                    m_axis_tuser_o  <= (px_cnt == 0) && (row_cnt == 0);
                end
            endcase
        end
    end

    // Pattern generation logic
    generate_pattern #(
        .WIDTH(WIDTH),
        .HEIGHT(HEIGHT),
        .DATA_WIDTH(DATA_WIDTH)
    ) pattern_inst (
        .x(px_cnt),
        .y(row_cnt),
        .sel_i(sel_i),
        .data_out(pattern_data)
    );

endmodule

// Pattern generation module
module generate_pattern #(
    parameter WIDTH = 1920,
    parameter HEIGHT = 1080,
    parameter DATA_WIDTH = 24
) (
    input  wire [$clog2(WIDTH)-1:0]  x,
    input  wire [$clog2(HEIGHT)-1:0] y,
    input  wire [2:0]                sel_i,
    output reg  [DATA_WIDTH-1:0]     data_out
);

    // Assuming RGB888 format (8 bits per channel)
    localparam CH_WIDTH = DATA_WIDTH / 3;

    wire [CH_WIDTH-1:0] gradient_h, gradient_v;

    wire checkerbrd;
    wire [2:0] colorbar_sel;

    // Calculate gradients
    assign gradient_h = (x * 256) / WIDTH;
    assign gradient_v = (y * 256) / HEIGHT;

    // checkerbrdboard pattern (32x32 squares)
    assign checkerbrd = ((x[5] ^ y[5]));

    // Color bar selection (8 bars)
    assign colorbar_sel = (x * 8) / WIDTH;

    // Pattern multiplexer
    always @(*) begin
        case (sel_i)
            3'd0: begin // Solid white
                data_out = {DATA_WIDTH{1'b1}};
            end

            3'd1: begin // Color bars (SMPTE-style)
                case (colorbar_sel)
                    3'd0: data_out = {8'hFF, 8'hFF, 8'hFF}; // White
                    3'd1: data_out = {8'hFF, 8'hFF, 8'h00}; // Yellow
                    3'd2: data_out = {8'h00, 8'hFF, 8'hFF}; // Cyan
                    3'd3: data_out = {8'h00, 8'hFF, 8'h00}; // Green
                    3'd4: data_out = {8'hFF, 8'h00, 8'hFF}; // Magenta
                    3'd5: data_out = {8'hFF, 8'h00, 8'h00}; // Red
                    3'd6: data_out = {8'h00, 8'h00, 8'hFF}; // Blue
                    3'd7: data_out = {8'h00, 8'h00, 8'h00}; // Black
                endcase
            end

            3'd2: begin // Horizontal gradient (white to black)
                data_out = {gradient_h, gradient_h, gradient_h};
            end

            3'd3: begin // Vertical gradient (white to black)
                data_out = {gradient_v, gradient_v, gradient_v};
            end

            3'd4: begin // checkerbrdboard
                data_out = checkerbrd ? {DATA_WIDTH{1'b1}} : {DATA_WIDTH{1'b0}};
            end

            3'd5: begin // Ramp pattern (diagonal gradient)
                data_out = {gradient_h[7:0], gradient_v[7:0],
                           ((gradient_h + gradient_v) >> 1)};
            end

            default: begin
                data_out = {DATA_WIDTH{1'b0}};
            end
        endcase
    end

    /* verilator lint_on WIDTHTRUNC */
    /* verilator lint_on WIDTHEXPAND */

endmodule
