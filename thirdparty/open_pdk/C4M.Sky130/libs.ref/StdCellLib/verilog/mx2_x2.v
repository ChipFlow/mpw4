/*                                                                      */
/*  Avertec Release v3.4p5 (64 bits on Linux 5.10.0-0.bpo.9-amd64)      */
/*  [AVT_only] host: fsdev                                              */
/*  [AVT_only] arch: x86_64                                             */
/*  [AVT_only] path: /opt/tasyag-3.4p5/bin/avt_shell                    */
/*  argv:                                                               */
/*                                                                      */
/*  User: verhaegs                                                      */
/*  Generation date Fri Dec 10 15:33:05 2021                            */
/*                                                                      */
/*  Verilog data flow description generated from `mx2_x2`               */
/*                                                                      */


`timescale 1 ps/1 ps

module mx2_x2 (q, cmd, i0, i1);

  output q;
  input  cmd;
  input  i0;
  input  i1;

  wire v_net5;
  wire v_net1;

  assign v_net1 = ((~(cmd) & ~(i0)) | (~(v_net5) & ~(i1)));
  assign v_net5 = ~(cmd);

  assign q = ~(v_net1);

endmodule
