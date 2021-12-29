/*                                                                      */
/*  Avertec Release v3.4p5 (64 bits on Linux 5.10.0-0.bpo.9-amd64)      */
/*  [AVT_only] host: fsdev                                              */
/*  [AVT_only] arch: x86_64                                             */
/*  [AVT_only] path: /opt/tasyag-3.4p5/bin/avt_shell                    */
/*  argv:                                                               */
/*                                                                      */
/*  User: verhaegs                                                      */
/*  Generation date Wed Dec 29 11:35:49 2021                            */
/*                                                                      */
/*  Verilog data flow description generated from `o4_x2`                */
/*                                                                      */


`timescale 1 ps/1 ps

module o4_x2 (q, i0, i1, i2, i3);

  output q;
  input  i0;
  input  i1;
  input  i2;
  input  i3;

  wire v_net2;

  assign v_net2 = (~(i3) & ~(i1) & ~(i0) & ~(i2));

  assign q = ~(v_net2);

endmodule
