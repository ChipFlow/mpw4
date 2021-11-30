import argparse, subprocess, sys
from pathlib import Path

from nmigen import *
from nmigen.back import verilog
from .test_soc import SoCWrapper

class FPGATop(Elaboratable):
    def __init__(self, build_dir):
        self.build_dir = build_dir
        self.io = Signal(38)
        self.ram_rstn = Signal()
        self.ports = [self.io, self.ram_rstn]

    def elaborate(self, platform):
        m = Module()
        soc = SoCWrapper(self.build_dir)
        m.submodules.soc = soc
        for i in range(38):
            m.submodules += Instance("BB",
                io_B=self.io[i],
                i_I=soc.io_out[i],
                i_T=soc.io_oeb[i],
                o_O=soc.io_in[i],
            )
        m.d.comb += self.ram_rstn.eq(1)
        return m

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-dir', default='./build/fpga')
    parser.add_argument('--build', action='store_true')
    parser.add_argument('--prog', action='store_true')
    parser.add_argument('--prog-fw', action='store_true')
    args = parser.parse_args(sys.argv[1:])

    if args.build:
        Path(args.build_dir).mkdir(parents=True, exist_ok=True)
        top = FPGATop(args.build_dir)
        output = verilog.convert(top, name="top", ports=top.ports)

        top_verilog = Path(args.build_dir) / "top.v"
        spimem_verilog = Path(__file__).parent.parent / "cores" / "spimemio.v"
        top_pdc = Path(__file__).parent / "crosslink_nx_vip.pdc"

        top_json = Path(args.build_dir) / "top.json"
        top_fasm = Path(args.build_dir) / "top.fasm"
        top_bit = Path(args.build_dir) / "top.bit"

        with open(top_verilog, "w") as f:
            f.write(output)
        subprocess.run(["yosys", "-ql", Path(args.build_dir) / "synth.log", "-p",
            f"synth_nexus -nowidelut -top top -json {top_json}",
            top_verilog, spimem_verilog], check=True)
        subprocess.run(["nextpnr-nexus", "--device", "LIFCL-40-8BG400CES",
            "--pdc", top_pdc, "--json", top_json, "--fasm", top_fasm], check=True)
        subprocess.run(["prjoxide", "pack", top_fasm, top_bit], check=True)

    if args.prog_fw:
        bios_bin = Path(args.build_dir) / "soc" / "bios" / "bios.bin"
        subprocess.run(["ecpprog", "-o", "1M", bios_bin])

    if args.prog:
        top_bit = Path(args.build_dir) / "top.bit"
        subprocess.run(["ecpprog", "-S", top_bit])

if __name__ == '__main__':
    main()
