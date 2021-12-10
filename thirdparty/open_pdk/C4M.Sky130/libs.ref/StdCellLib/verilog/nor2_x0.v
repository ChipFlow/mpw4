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
/*  Verilog data flow description generated from `nor2_x0`              */
/*                                                                      */


`timescale 1 ps/1 ps

module nor2_x0 (nq, i0, i1);

  output nq;
  input  i0;
  input  i1;


  assign nq = (~(i1) & ~(i0));

endmodule