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
/*  Verilog data flow description generated from `a3_x2`                */
/*                                                                      */


`timescale 1 ps/1 ps

module a3_x2 (q, i0, i1, i2);

  output q;
  input  i0;
  input  i1;
  input  i2;

  wire v_net1;

  assign v_net1 = (~(i2) | ~(i1) | ~(i0));

  assign q = ~(v_net1);

endmodule
