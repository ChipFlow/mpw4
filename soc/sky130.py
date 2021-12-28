import argparse, subprocess, sys, os
from pathlib import Path

from amaranth import *
from amaranth.back import verilog
from .test_soc import SoCWrapper

class Sky130Top(Elaboratable):
    def __init__(self, build_dir, small=False, with_bios=False):
        self.build_dir = build_dir
        self.with_bios = with_bios
        self.small = small
        self.io_out = Signal(38)
        self.io_oeb = Signal(38)
        self.io_in = Signal(38)
        self.ports = [self.io_in, self.io_out, self.io_oeb]

    def elaborate(self, platform):
        m = Module()
        soc = SoCWrapper(self.build_dir, small=self.small, with_bios=self.with_bios)
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

def do_fixup(args):
    # TODO: make this importable
    script = str(Path(__file__).parent.parent / "thirdparty/open_pdk/C4M.Sky130/libs.tech/klayout/bin/conv_c4msky130_to_sky130.py")
    subprocess.run(["python3", script,  "user_project_wrapper.gds", "user_project_wrapper_fixedup.gds"], check=True)

def do_pnr(args):
    os.chdir(args.build_dir)
    import CRL, Hurricane as Hur, Katana, Etesian, Anabatic, Cfg
    from Hurricane import DataBase, Transformation, Box, Instance
    from helpers import u, l, setNdaTopDir
    from helpers.overlay import CfgCache, UpdateSession

    sys.path.append(str(Path(__file__).parent.parent / "thirdparty/open_pdk/C4M.Sky130/libs.tech/coriolis/techno/etc/coriolis2"))
    from node130 import sky130 as tech
    tech.setup()
    tech.StdCellLib_setup()

    from plugins.alpha.block.block         import Block
    from plugins.alpha.block.configuration import IoPin, GaugeConf
    from plugins.alpha.block.spares        import Spares
    from plugins.alpha.chip.configuration  import ChipConf
    from plugins.alpha.chip.chip           import Chip
    from plugins.alpha.core2chip.sky130    import CoreToChip

    cell_name = "user_project_core_lambdasoc"
    cell = CRL.Blif.load(cell_name)

    af = CRL.AllianceFramework.get()
    env = af.getEnvironment()
    env.setCLOCK('io_in_from_pad(0)')

    lg5 = af.getRoutingGauge('StdCellLib').getLayerGauge( 5 )
    lg5.setType( CRL.RoutingLayerGauge.PowerSupply )

    conf = ChipConf( cell, ioPins=[], ioPads=[] ) 
    conf.cfg.etesian.bloat               = 'Flexlib'
    conf.cfg.etesian.uniformDensity      = True
    conf.cfg.etesian.aspectRatio         = 1.0
   # etesian.spaceMargin is ignored if the coreSize is directly set.
    conf.cfg.etesian.spaceMargin         = 0.10
    conf.cfg.etesian.antennaGateMaxWL = u(400.0)
    conf.cfg.etesian.antennaDiodeMaxWL = u(800.0)
    conf.cfg.etesian.feedNames = 'tie_diff'
    conf.cfg.anabatic.searchHalo         = 2
    conf.cfg.anabatic.globalIterations   = 20
    conf.cfg.anabatic.topRoutingLayer    = 'm4'
    conf.cfg.katana.hTracksReservedLocal = 25
    conf.cfg.katana.vTracksReservedLocal = 20
    conf.cfg.katana.hTracksReservedMin   = 12
    conf.cfg.katana.vTracksReservedMin   = 10
    conf.cfg.katana.trackFill            = 0
    conf.cfg.katana.runRealignStage      = True
    conf.cfg.katana.dumpMeasures         = True
    conf.cfg.katana.longWireUpReserve1   = 3.0
    conf.cfg.block.spareSide             = u(7*10)
    conf.cfg.chip.minPadSpacing          = u(1.46)
    conf.cfg.chip.supplyRailWidth        = u(20.0)
    conf.cfg.chip.supplyRailPitch        = u(40.0)
    conf.cfg.harness.path                = str(Path(__file__).parent.parent / 'resources' / 'user_project_wrapper.def')
    conf.useSpares           = True
    # conf.useClockTree        = True
    # conf.useHFNS             = True
    conf.bColumns            = 2
    conf.bRows               = 2
    conf.chipName            = 'chip'
    if args.small:
        conf.coreSize            = ( u( 160*10.0), u( 160*10.0) )
    else:
        conf.coreSize            = ( u( 210*10.0), u( 210*10.0) )
    conf.useHTree( 'io_in_from_pad(0)', Spares.HEAVY_LEAF_LOAD )

    coreToChip = CoreToChip( conf )
    coreToChip.buildChip()
    chipBuilder = Chip( conf )
    chipBuilder.doChipFloorplan()
    chipBuilder.doPnR()
    chipBuilder.save()
    do_fixup(args)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--build-dir', default='./build/sky130')
    parser.add_argument('--with-bios', action='store_true')
    parser.add_argument('--small', action='store_true')
    parser.add_argument('--synth', action='store_true')
    parser.add_argument('--pnr', action='store_true')
    args = parser.parse_args(sys.argv[1:])

    Path(args.build_dir).mkdir(parents=True, exist_ok=True)

    if args.synth:
        top = Sky130Top(args.build_dir, small=args.small, with_bios=args.with_bios)
        output = verilog.convert(top, name="user_project_core_lambdasoc", ports=top.ports)

        top_verilog = Path(args.build_dir) / "top.v"
        spimem_verilog = Path(__file__).parent.parent / "cores" / "spimemio.v"
        abc_constr = Path(__file__).parent.parent / "soc" / "abc.constr"
        liberty = Path(__file__).parent.parent / "thirdparty/open_pdk/C4M.Sky130/libs.ref/StdCellLib/liberty/StdCellLib_slow.lib"

        with open(top_verilog, "w") as f:
            f.write(output)

        target_delay = 20000 # 50MHz
        max_fanout = 64
        synth_script = f"""
read_liberty -lib {liberty}
read_verilog {top_verilog} {spimem_verilog}
synth -flatten -top user_project_core_lambdasoc
dfflibmap -liberty {liberty}
opt
abc -script +strash;ifraig;scorr;dc2;dretime;strash;&get,-n;&dch,-f;&nf,-D,{target_delay};&put;buffer,-G,1000,-N,{max_fanout};upsize,-D,{target_delay};dnsize,-D,{target_delay};stime,-p -constr {abc_constr} -liberty {liberty}
setundef -zero
clean -purge
write_blif {args.build_dir}/user_project_core_lambdasoc.blif
write_json {args.build_dir}/user_project_core_lambdasoc.json
stat"""
        top_ys = Path(args.build_dir) / "top.ys"
        with open(top_ys, "w") as f:
            print(synth_script, file=f)
        subprocess.run(["yosys", "-ql", Path(args.build_dir) / "synth.log", top_ys], check=True)
    if args.pnr:
        do_pnr(args)

if __name__ == '__main__':
    main()
