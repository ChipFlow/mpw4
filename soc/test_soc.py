import argparse
import importlib

from amaranth import *
from thirdparty.amaranth_soc import wishbone

from thirdparty.lambdasoc.cpu.minerva import MinervaCPU
from thirdparty.lambdasoc.periph.intc import GenericInterruptController
from thirdparty.lambdasoc.periph.serial import AsyncSerialPeripheral
from thirdparty.lambdasoc.periph.sram import SRAMPeripheral
from thirdparty.lambdasoc.periph.timer import TimerPeripheral
from thirdparty.lambdasoc.soc.cpu import CPUSoC

from cores.gpio import GPIOPeripheral
from cores.spimemio_wrapper import SPIMemIO
from cores.hyperram import HyperRAM

class HyperRamSoC(CPUSoC, Elaboratable):
    def __init__(self, *, reset_addr, clk_freq,
                 rom_addr, flash_ctrl_addr, flash_pins,
                 hram_addr, hyperram_pins,
                 sram_addr, sram_size,
                 uart_addr, uart_divisor, uart_pins,
                 timer_addr, timer_width,
                 gpio_addr, gpio_count, gpio_pins):
        self._arbiter = wishbone.Arbiter(addr_width=30, data_width=32, granularity=8)
        self._decoder = wishbone.Decoder(addr_width=30, data_width=32, granularity=8)

        self.cpu = MinervaCPU(reset_address=reset_addr, with_muldiv=True)
        self._arbiter.add(self.cpu.ibus)
        self._arbiter.add(self.cpu.dbus)

        self.rom = SPIMemIO(flash=flash_pins)
        self._decoder.add(self.rom.data_bus, addr=rom_addr)
        self._decoder.add(self.rom.ctrl_bus, addr=flash_ctrl_addr)

        self.ram = SRAMPeripheral(size=sram_size)
        self._decoder.add(self.ram.bus, addr=sram_addr)

        self.hyperram = HyperRAM(io=hyperram_pins)
        self._decoder.add(self.hyperram.bus, addr=hram_addr)        

        self.uart = AsyncSerialPeripheral(divisor=uart_divisor, pins=uart_pins, rx_depth=4, tx_depth=4)
        self._decoder.add(self.uart.bus, addr=uart_addr)

        self.timer = TimerPeripheral(width=timer_width)
        self._decoder.add(self.timer.bus, addr=timer_addr)

        self.intc = GenericInterruptController(width=len(self.cpu.ip))
        self.intc.add_irq(self.timer.irq, 0)
        self.intc.add_irq(self.uart .irq, 1)

        self.gpio = GPIOPeripheral(gpio_count, gpio_pins)
        self._decoder.add(self.gpio.bus, addr=gpio_addr)

        self.memory_map = self._decoder.bus.memory_map

        self.clk_freq = clk_freq

    def elaborate(self, platform):
        m = Module()

        m.submodules.arbiter  = self._arbiter
        m.submodules.cpu      = self.cpu

        m.submodules.decoder  = self._decoder
        m.submodules.rom      = self.rom
        m.submodules.ram      = self.ram
        m.submodules.hyperram = self.hyperram
        m.submodules.uart     = self.uart
        m.submodules.timer    = self.timer
        m.submodules.gpio     = self.gpio
        m.submodules.intc     = self.intc

        m.d.comb += [
            self._arbiter.bus.connect(self._decoder.bus),
            self.cpu.ip.eq(self.intc.ip),
        ]

        return m

def parse_pinout():
    result = {}
    import pathlib
    with open(pathlib.Path(__file__).parent / "pinout_plan.txt", "r") as f:
        for line in f:
            sl = [x for x in line.strip().split(' ') if x]
            if len(sl) != 2: continue
            result[sl[1]] = int(sl[0])
    return result

# Create a pretend UART resource with arbitrary signals
class UARTPins():
    class Input():
        def __init__(self, sig):
            self.i = sig
    class Output():
        def __init__(self, sig):
            self.o = sig
    def __init__(self, rx, tx):
        self.rx = UARTPins.Input(rx)
        self.tx = UARTPins.Output(tx)


class SoCWrapper(Elaboratable):
    def __init__(self, build_dir="build", with_bios=True):
        io_count = 38
        self.build_dir = build_dir
        self.with_bios = with_bios
        self.io_in = Signal(io_count)
        self.io_out = Signal(io_count)
        self.io_oeb = Signal(io_count)
        self.pinout = parse_pinout()

    def i(self, name): return self.io_in[self.pinout[name]]
    def o(self, name): return self.io_out[self.pinout[name]]
    def oeb(self, name): return self.io_oeb[self.pinout[name]]

    def elaborate(self, platform):
        m = Module()

        # Gets i, o, oeb in a dict for all pins starting with a prefix
        def resource_pins(resource):
            result = {}
            for pin, bit in self.pinout.items():
                if pin.startswith(resource):
                    bit_name = pin[len(resource):]
                    result[f"{bit_name}_i"] = Signal()
                    result[f"{bit_name}_o"] = Signal()
                    result[f"{bit_name}_oeb"] = Signal()
                    m.d.comb += [
                        self.io_out[bit].eq(result[f"{bit_name}_o"]),
                        self.io_oeb[bit].eq(result[f"{bit_name}_oeb"]),
                        result[f"{bit_name}_i"].eq(self.io_in[bit]),
                    ]
            return result

        # Clock input
        m.domains.sync = ClockDomain(async_reset=False)
        m.d.comb += ClockSignal().eq(self.i("clk"))
        # Reset synchroniser
        rst = Signal()
        m.d.comb += rst.eq(~self.i("rstn"))
        rst_sync0 = Signal(reset_less=True)
        rst_sync1 = Signal(reset_less=True)
        m.d.sync += [
            rst_sync0.eq(rst),
            rst_sync1.eq(rst_sync0),
        ]
        m.d.comb += [
            ResetSignal().eq(rst_sync1),
            self.o("rst_inv_out").eq(rst), # mirror to some pins for debugging
            self.o("rst_sync_out").eq(rst_sync1),
        ]

        uart_pins = UARTPins(rx=self.i("uart_rx"), tx=self.o("uart_tx"))

        # The SoC itself
        m.submodules.soc = HyperRamSoC(
            reset_addr=0x00100000, clk_freq=int(27e6),
            rom_addr=0x00000000, flash_ctrl_addr=0x10007000, flash_pins=resource_pins("flash_"),
            hram_addr=0x20000000, hyperram_pins=resource_pins("ram_"),
            sram_addr=0x10004000, sram_size=0x200,
            uart_addr=0x10005000, uart_divisor=int(27e6 // 9600), uart_pins=uart_pins,
            timer_addr=0x10006000, timer_width=32,
            gpio_addr=0x10008000, gpio_count=8, gpio_pins=resource_pins("gpio_"),
        )
        if self.with_bios:
            m.submodules.soc.build(build_dir=f"{self.build_dir}/soc", do_init=True)
        # Heartbeat counter so we can confirm basic logic works
        hb_ctr = Signal(24)
        m.d.sync += hb_ctr.eq(hb_ctr + 1)
        m.d.comb += [
            self.o("heartbeat_0").eq(hb_ctr[0]),
            self.o("heartbeat_1").eq(hb_ctr[23]),
        ]
        # Remaining pins
        for pin, bit in self.pinout.items():
            if pin in ("clk", "rstn", "uart_rx") or pin.startswith("unalloc_"): # inputs and TODOs
                m.d.comb += [
                    self.io_oeb[bit].eq(1),
                    self.io_out[bit].eq(0),
                ]
            elif pin.startswith("heartbeat") or pin in ("rst_inv_out", "rst_sync_out", "uart_tx"): # outputs
                m.d.comb += [
                    self.io_oeb[bit].eq(0),
                ]
        return m

if __name__ == "__main__":
    wrapper = SoCWrapper()
    from amaranth.cli import main
    main(wrapper, name="soc_wrapper", ports=[wrapper.io_in, wrapper.io_out, wrapper.io_oeb])
