import argparse, subprocess, sys, os
from pathlib import Path

from amaranth import *
from amaranth.back import verilog
from .test_soc import SoCWrapper

class Sky130Top(Elaboratable):
    def __init__(self, build_dir, with_bios=False):
        self.build_dir = build_dir
        self.with_bios = with_bios
        self.io_out = Signal(38)
        self.io_oeb = Signal(38)
        self.io_in = Signal(38)
        self.ports = [self.io_in, self.io_out, self.io_oeb]

    def elaborate(self, platform):
        m = Module()
        soc = SoCWrapper(self.build_dir, with_bios=self.with_bios)
        m.submodules.soc = soc
        for i in range(38):
            # Prevent identical signals being merged using an explicit buffer
            m.submodules += Instance("buf_x1",
                i_i=soc.io_oeb[i],
                o_q=self.io_oeb[i],
                a_keep=True
            )
            m.submodules += Instance("buf_x1",
                i_i=soc.io_out[i],
                o_q=self.io_out[i],
                a_keep=True
            )
        m.d.comb += soc.io_in.eq(self.io_in)
        return m


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-dir', default='./build/sky130')
    parser.add_argument('--with-bios', action='store_true')
    parser.add_argument('--synth', action='store_true')
    parser.add_argument('--pnr', action='store_true')
    args = parser.parse_args(sys.argv[1:])

    Path(args.build_dir).mkdir(parents=True, exist_ok=True)

    if args.synth:
        top = Sky130Top(args.build_dir, with_bios=args.with_bios)
        output = verilog.convert(top, name="user_project_core_lambdasoc", ports=top.ports)

        top_verilog = Path(args.build_dir) / "top.v"
        spimem_verilog = Path(__file__).parent.parent / "cores" / "spimemio.v"
        abc_constr = Path(__file__).parent.parent / "soc" / "abc.constr"
        liberty = Path(__file__).parent.parent / "thirdparty/open_pdk/C4M.Sky130/libs.ref/StdCellLib/liberty/StdCellLib_slow.lib"

        with open(top_verilog, "w") as f:
            f.write(output)

        synth_script = f"""
read_liberty -lib {liberty}
read_verilog {top_verilog} {spimem_verilog}
synth -flatten -top user_project_core_lambdasoc
dfflibmap -liberty {liberty}
opt
abc -D 200000 -constr {abc_constr} -liberty {liberty}
setundef -zero
clean -purge
write_blif {args.build_dir}/user_project_core_lambdasoc.blif
write_json {args.build_dir}/user_project_core_lambdasoc.json
stat"""
        top_ys = Path(args.build_dir) / "top.ys"
        with open(top_ys, "w") as f:
            print(synth_script, file=f)
        subprocess.run(["yosys", "-ql", Path(args.build_dir) / "synth.log", top_ys], check=True)

if __name__ == '__main__':
    main()
