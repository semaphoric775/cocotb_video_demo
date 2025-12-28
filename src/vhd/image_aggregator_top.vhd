library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library work;
use work.image_aggregator_pkg.all;

entity image_aggregator_top is
port (
    -- Clock and Reset
    clk_i          : in  std_logic;
    rstn_i         : in  std_logic;

    -- AXI Stream Input 0 (Top-Left quadrant)
    s0_axis_i       : in  t_axis_rec;
    s0_tready_o     : out t_axis_tready;

    -- AXI Stream Input 1 (Top-Right quadrant)
    s1_axis_i       : in  t_axis_rec;
    s1_tready_o     : out t_axis_tready;

    -- AXI Stream Input 2 (Bottom-Left quadrant)
    s2_axis_i       : in  t_axis_rec;
    s2_tready_o     : out t_axis_tready;

    -- AXI Stream Input 3 (Bottom-Right quadrant)
    s3_axis_i       : in  t_axis_rec;
    s3_tready_o     : out t_axis_tready;

    -- AXI Stream Output (Aggregated image)
    m_axis_o        : out t_axis_rec;
    m_tready_i      : in  t_axis_tready;

    -- Resync request output to further up video pipeline
    --  handles case of AXI Stream backpressure errors
    resync_req_o    : out std_logic
);
end image_aggregator_top;

architecture rtl of image_aggregator_top is

type t_state is (S_RESET, S_WAIT_SOF, S_IMG0, S_IMG1, S_IMG2, S_IMG3, S_ERR, S_DONE);

signal curr_state : t_state;
signal state_next : t_state;

-- Output image dimensions (2x input in each dimension)
--  assume identically sized frames from every source
constant C_OUTPUT_WIDTH  : integer := C_PIXELS_PER_ROW * 2;
constant C_OUTPUT_HEIGHT : integer := C_ROWS_PER_IMAGE * 2;

-- range at 0 to avoid initialization issues in simulation
signal pixel_cnt  : integer range 0 to C_OUTPUT_WIDTH;
signal row_cnt    : integer range 0 to C_OUTPUT_HEIGHT;

signal axis_err   : std_logic;
signal img0_sof : std_logic;

begin

img0_sof <= s0_axis_i.tvalid and s0_axis_i.tuser;
axis_err <= '1' when (m_axis_o.tvalid = '1' and m_tready_i.tready = '0') else '0';

proc_sm_reg : process(clk_i, rstn_i)
begin
    if rstn_i = '0' then
        curr_state  <= S_RESET;
    elsif rising_edge(clk_i) then
        curr_state  <= state_next;
    end if;
end process;

proc_sm_nextstate : process(all)
begin
    case curr_state is
        when S_RESET =>
            state_next <= S_WAIT_SOF;

        when S_WAIT_SOF =>
            state_next <= S_IMG0 when img0_sof = '1' else S_WAIT_SOF;

        when S_IMG0 =>
            if (pixel_cnt = C_PIXELS_PER_ROW) then
                state_next <= S_IMG1;
            end if;

        when S_IMG1 =>
            if (pixel_cnt = C_PIXELS_PER_ROW and row_cnt = C_ROWS_PER_IMAGE) then
                state_next <= S_IMG2;
            elsif (pixel_cnt = C_PIXELS_PER_ROW) then
                state_next <= S_IMG0;
            end if;

        when S_IMG2 =>
            if (pixel_cnt = C_PIXELS_PER_ROW) then
                state_next <= S_IMG3;
            end if;

        when S_IMG3 =>
            if (pixel_cnt = C_PIXELS_PER_ROW and row_cnt = C_OUTPUT_HEIGHT) then
                state_next <= S_DONE;
            elsif (pixel_cnt = C_PIXELS_PER_ROW) then
                state_next <= S_IMG2;
            end if;

        when S_DONE =>
            state_next <= S_WAIT_SOF;

        when S_ERR =>
            state_next <= S_WAIT_SOF;
    end case;
end process;

proc_counters : process (clk_i) begin
    if rising_edge(clk_i) then
        if curr_state = S_RESET or curr_state = S_DONE or curr_state = S_ERR then
            pixel_cnt <= 1;
            row_cnt   <= 1;
        else
            if pixel_cnt = C_PIXELS_PER_ROW then
                pixel_cnt <= 1;
                row_cnt   <= row_cnt + 1;
            -- only count accepted transactions
            elsif (m_axis_o.tvalid = '1' and m_tready_i.tready = '1') then
                pixel_cnt <= pixel_cnt + 1;
            end if;

            if row_cnt = C_OUTPUT_HEIGHT then
                row_cnt <= 1;
            end if;

        end if;
    end if;
end process;

proc_mux : process (all)
begin
    case curr_state is
        when S_IMG0 =>
            m_axis_o.tdata <= s0_axis_i.tdata;
            m_axis_o.tvalid <= s0_axis_i.tvalid;
            m_axis_o.tlast <= s0_axis_i.tlast;

        when S_IMG1 =>
            m_axis_o.tdata <= s1_axis_i.tdata;
            m_axis_o.tvalid <= s1_axis_i.tvalid;
            m_axis_o.tlast <= s1_axis_i.tlast;

        when S_IMG2 =>
            m_axis_o.tdata <= s2_axis_i.tdata;
            m_axis_o.tvalid <= s2_axis_i.tvalid;
            m_axis_o.tlast <= s2_axis_i.tlast;

        when S_IMG3 =>
            m_axis_o.tdata <= s3_axis_i.tdata;
            m_axis_o.tvalid <= s3_axis_i.tvalid;
            m_axis_o.tlast <= s3_axis_i.tlast;

        when others =>
            m_axis_o.tdata <= s0_axis_i.tdata;
            m_axis_o.tvalid <= s0_axis_i.tvalid;
            m_axis_o.tlast <= s0_axis_i.tlast;

    end case;
end process;

m_axis_o.tuser <= img0_sof;

-- Assume AXI Stream behavior
--   can be implemented with FWFT FIFO
s0_tready_o.tready <= '1' when (curr_state = S_IMG0  or curr_state = S_WAIT_SOF) else '0';
s1_tready_o.tready <= '1' when (curr_state = S_IMG1 ) else '0';
s2_tready_o.tready <= '1' when (curr_state = S_IMG2 ) else '0';
s3_tready_o.tready <= '1' when (curr_state = S_IMG3 ) else '0';

resync_req_o <= '1' when (curr_state = S_ERR) else '0';

end rtl;
