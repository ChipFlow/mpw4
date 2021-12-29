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
/*  Verilog data flow description generated from `buf_x1`               */
/*                                                                      */


`timescale 1 ps/1 ps

module buf_x1 (i, q);

  input  i;
  output q;

  wire ni;

  assign ni = ~(i);

  assign q = ~(ni);

endmodule
