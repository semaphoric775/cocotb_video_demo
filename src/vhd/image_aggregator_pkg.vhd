library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package image_aggregator_pkg is

    -- Image configuration constants
    constant C_PIXELS_PER_ROW    : integer := 640;
    constant C_ROWS_PER_IMAGE    : integer := 480;
    constant C_PIXEL_WIDTH       : integer := 24;  -- RGB888 format
    constant C_BYTES_PER_PIXEL   : integer := 3;   -- 3 bytes for RGB888

    constant C_AXIS_TDATA_WIDTH  : integer := C_PIXEL_WIDTH;  -- AXI Stream data width
    constant C_PIXELS_PER_IMAGE  : integer := C_PIXELS_PER_ROW * C_ROWS_PER_IMAGE;

    -- AXI Stream Master record
    type t_axis_rec is record
        tdata  : std_logic_vector(C_AXIS_TDATA_WIDTH-1 downto 0);
        tvalid : std_logic;
        tlast  : std_logic;
        tuser  : std_logic;  -- Start of frame
    end record t_axis_rec;

    -- AXI Stream Output backpressure
    type t_axis_tready is record
        tready : std_logic;
    end record t_axis_tready;

end package image_aggregator_pkg;
