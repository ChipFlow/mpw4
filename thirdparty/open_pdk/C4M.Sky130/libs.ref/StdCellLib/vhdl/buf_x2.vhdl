--  
--  Avertec Release v3.4p5 (64 bits on Linux 5.10.0-0.bpo.9-amd64)
--  [AVT_only] host: fsdev
--  [AVT_only] arch: x86_64
--  [AVT_only] path: /opt/tasyag-3.4p5/bin/avt_shell
--  argv: 
--  
--  User: verhaegs
--  Generation date Wed Dec 29 11:35:49 2021
--  
--  VHDL data flow description generated from `buf_x2`
--  

library IEEE;
use IEEE.std_logic_1164.all;

-- Entity Declaration

ENTITY buf_x2 IS
  PORT (
         i : in    STD_LOGIC;
         q : out   STD_LOGIC
  );
END buf_x2;

-- Architecture Declaration

ARCHITECTURE RTL OF buf_x2 IS
  SIGNAL ni : STD_LOGIC;

BEGIN


  ni <= not (i);

  q <= not (ni);

END;
