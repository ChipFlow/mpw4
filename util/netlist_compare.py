#!/usr/bin/env python3
import sys, json
from enum import Enum
from dataclasses import dataclass, field
from collections import namedtuple
from typing import Optional, NamedTuple

"""
netlist_compare does comparison between Yosys JSON and extracted SPICE netlists

It is also used for other ad hoc post-pnr checks, for example that clock trees are correctly balanced
and (soon) power rails are correctly connected.
"""


# Design config, we should separate this off somehow
top_power = "vccd1"
top_ground = "vssd1"
local_power = "vdd"
local_ground = "vss"
power_pins = {"vdd", }
ground_pins = {"vss", }
const_zeros = {"zero_x1", }
const_ones = {"one_x1", }

buffers = {"buf_x8", "buf_x4", "buf_x2", }
buffer_ports = ("i", "q")

dffs = {"sff1_x4", "sff1r_x4"}
dff_clk = "ck"
extra_boxes = {"decap_w0", "zero_x1", "one_x1"}

def is_power_net(n):
    return n == top_power or n == top_ground or n == local_ground or n.startswith(local_power)

class PortDir(Enum):
    INPUT = 0
    OUTPUT = 1
    INOUT = 2
    GROUND = 3
    POWER = 4
    UNKNOWN = -1

@dataclass
class ModulePort:
   name: str
   direction: PortDir
   net: Optional[str] = None

@dataclass
class CellInst:
    name: str
    cell_type: str
    ports: dict[str, str] = field(default_factory=dict)

class InstPortRef(NamedTuple):
    inst: str
    port: str

@dataclass
class Net:
    name: str
    driver: Optional[InstPortRef] = None
    users: set[InstPortRef] = field(default_factory=set)
    power_gnds: set[InstPortRef] = field(default_factory=set)
    buffer_depth: dict[InstPortRef, int] = field(default_factory=dict)

@dataclass
class Module:
    name: str
    blackbox: bool = False
    ports: dict[str, ModulePort] = field(default_factory=dict)
    insts: dict[str, CellInst] = field(default_factory=dict)
    nets: dict[str, Net] = field(default_factory=dict)

    def get_dir(self, port):
        if port in power_pins:
            return PortDir.POWER
        elif port in ground_pins:
            return PortDir.GROUND
        else:
            return self.ports[port].direction

    def link(self, lib):
        # During netlist import we only set up the CellInst.ports dict
        # This takes those values and builds up nets with driver/users set
        # 'lib' is a module that contains the definitions for library cells so port directions can be known
        error_count = 0

        def err(s):
            nonlocal error_count
            print(s, file=sys.stderr)
            error_count += 1

        for port_data in self.ports.values():
            if port_data.net is None: continue
            if port_data.net in self.nets: continue
            self.nets[port_data.net] = Net(name=port_data.net)
        for inst_name, inst_data in self.insts.items():
            if inst_data.cell_type in const_ones or inst_data.cell_type in const_zeros:
                # Special case as not in synth library
                for port_name, net in inst_data.ports.items():
                    if port_name in (local_power, local_ground):
                        continue
                    if net not in self.nets:
                        self.nets[net] = Net(name=net)
                    net_data = self.nets[net]
                    if is_power_net(net):
                        err(f"output '{inst_name}.{port_name}' shorted to power net '{net}'")
                        continue
                    elif net_data.driver is not None:
                        err(f"net '{net}' multiply driven by '{net_data.driver}' and '{inst_name}.{port_name}'")
                    net_data.driver = InstPortRef(inst_name, port_name)
                continue
            if inst_data.cell_type in extra_boxes:
                continue
            if inst_data.cell_type not in lib.modules:
                assert False, f"instance '{inst_name}' type {inst_data.cell_type} not found in library"
            lib_cell = lib.modules[inst_data.cell_type]
            for port_name, net in inst_data.ports.items():
                if net not in self.nets:
                    self.nets[net] = Net(name=net)
                net_data = self.nets[net]
                port_dir = lib_cell.get_dir(port_name)
                if port_dir == PortDir.OUTPUT:
                    if is_power_net(net):
                        err(f"output '{inst_name}.{port_name}' shorted to power net '{net}'")
                        continue
                    elif net_data.driver is not None:
                        err(f"net '{net}' multiply driven by '{net_data.driver}' and '{inst_name}.{port_name}'")
                    net_data.driver = InstPortRef(inst_name, port_name)
                elif port_dir in (PortDir.POWER, PortDir.GROUND):
                    net_data.power_gnds.add(InstPortRef(inst_name, port_name))
                elif port_dir in (PortDir.INPUT, PortDir.INOUT):
                    net_data.users.add(InstPortRef(inst_name, port_name))
                else:
                    assert False, port_dir
        return error_count

    def flatten(self, lib):
        work_queue = []
        for inst in self.insts.values():
            work_queue.append(inst)
        while len(work_queue) > 0:
            inst = work_queue.pop()
            if inst.cell_type not in lib.modules:
                continue
            inst_mod = lib.modules[inst.cell_type]
            # Don't flatten blackBlackboxboxes
            if inst_mod.blackbox:
                continue
            net_map = {}
            for port_name, port_data in inst_mod.ports.items():
                if port_name not in inst.ports:
                    continue
                top_net = inst.ports[port_name]
                if top_net is None or port_data.net is None:
                    continue
                net_map[port_data.net] = top_net
            for net in inst_mod.nets.keys():
                if net in net_map:
                    continue
                top_net = Net(name=f"{inst.name}/{net.name}")
                self.nets[top_net.name] = top_net
                net_map[net.name] = top_net.name
            for inst_name, inst_data in inst_mod.insts.items():
                top_inst = CellInst(name=f"{inst.name}/{inst_name}", cell_type=inst_data.cell_type)
                for inst_port, inst_net in inst_data.ports.items():
                    top_inst.ports[inst_port] = net_map[inst_net]
                # Recursively flatten
                self.insts[top_inst.name] = top_inst
                work_queue.append(top_inst) 
            del self.insts[inst.name]

    def write_json(self, lib, out_file):
        modules_out = {}
        # Blackboxes
        top_mod_out = {}
        net2idx = {"$const0": 0, "$const1": 1}
        def get_idx(net):
            if net in net2idx:
                return net2idx[net]
            else:
                idx = len(net2idx)
                net2idx[net] = idx
                return idx
        grouped_ports = {}
        # Reassemble bus ports
        for port in self.ports.values():
            if is_power_net(port.name):
                continue
            br_idx = port.name.rfind('[')
            if br_idx == -1:
                grouped_ports[port.name] = {0: port.name}
                continue
            basename = port.name[:br_idx]
            index = int(port.name[br_idx+1:-1])
            if basename not in grouped_ports: grouped_ports[basename] = {}
            grouped_ports[basename][index] = port.name
        ports_out = {}
        for basename, group in grouped_ports.items():
            ports_out[basename] = {}
            ports_out[basename]["direction"] = lib.modules[self.name].ports[group[0]].direction.name.lower()
            ports_out[basename]["bits"] = [get_idx(self.ports[p].net) for (i, p) in sorted(group.items(), key=lambda x: x[0])]

        cells_out = {}
        for inst in self.insts.values():
            lib_mod = lib.modules[inst.cell_type]
            cells_out[inst.name] = {}
            cells_out[inst.name]["type"] = inst.cell_type
            cells_out[inst.name]["port_directions"] = {}
            cells_out[inst.name]["connections"] = {}
            for port, net in inst.ports.items():
                if port not in lib_mod.ports:
                    continue
                cells_out[inst.name]["port_directions"][port] = lib_mod.ports[port].direction.name.lower()
                cells_out[inst.name]["connections"][port] = [get_idx(net)]

        netnames_out = {}
        for name, idx in net2idx.items():
            netnames_out[name] = dict(bits=[idx])

        top_mod_out["ports"] = ports_out
        top_mod_out["cells"] = cells_out
        top_mod_out["netnames"] = netnames_out
        modules_out[self.name] = top_mod_out
        print(json.dumps(dict(modules=modules_out), sort_keys=True, indent=4), file=out_file)

@dataclass
class Design:
    modules: dict[str, Module] = field(default_factory=dict)
    def rename_module(self, old, new):
        self.modules[new] = self.modules[old]
        self.modules[new].name = new
        del self.modules[old]

# Read in a JSON netlist from Yosys
def import_yosys_json(fp):
    j = json.load(fp)
    des = Design()
    for mod_name, mod_data in j["modules"].items():
        mod = Module(name=mod_name)
        if "attributes" in mod_data:
            attrs = mod_data["attributes"]
            if "blackbox" in attrs and int(attrs["blackbox"]) != 0: mod.blackbox = True
            if "whitebox" in attrs and int(attrs["whitebox"]) != 0: mod.blackbox = True
        idx2netname = {0: "$const0", 1: "$const1"}
        def idx2net(idx):
            if idx == "x":
                return "$undef"
            elif int(idx) in idx2netname:
                return idx2netname[int(idx)]
            else:
                return f"$net${int(idx)}$"
        if "netnames" in mod_data:
            for net_name, net_data in mod_data["netnames"].items():
                for i, bit in enumerate(net_data["bits"]):
                    if bit == "x":
                        continue
                    if int(bit) not in idx2netname:
                        idx2netname[int(bit)] = f"{net_name}[{i}]" if len(net_data["bits"]) > 1 else net_name
        if "ports" in mod_data:
            for port_name, port_data in mod_data["ports"].items():
                port_dir = PortDir[port_data["direction"].upper()]
                for i, bit in enumerate(port_data["bits"]):
                    bit_name = f"{port_name}[{i}]" if len(port_data["bits"]) > 1 else port_name
                    mod.ports[bit_name] = ModulePort(name=bit_name, direction=port_dir, net=idx2net(bit))
        if not mod.blackbox and "cells" in mod_data:
            for cell_name, cell_data in mod_data["cells"].items():
                inst = CellInst(name=cell_name, cell_type=cell_data["type"])
                for port_name, bits in cell_data["connections"].items():
                    for i, bit in enumerate(bits):
                        bit_name = f"{port_name}[{i}]" if len(bits) > 1 else port_name
                        inst.ports[bit_name] = idx2net(bit)
                mod.insts[inst.name] = inst
        des.modules[mod.name] = mod
    return des

def fix_brackets(n):
    # Coriolis uses VHDL-style () rather than Verilog-style []
    return n.replace('(', '[').replace(')', ']').replace("_from_pad", "").replace("_to_pad", "")

def fix_modname(n):
    if n.endswith("_pnr"):
        return n[:-4]
    return n

# Read in an extracted SPICE netlist from Magic
# 'lib' should be the design imported from Yosys with library cell definitions
def import_spice(lib, fp):
    lines = []
    for line in fp:
        l = line.split('*')[0].strip()
        if l.startswith('+') and len(lines) > 0:
            lines[-1] += l[1:] # continuation
        elif len(l) > 0:
            lines.append(l)
    # Work out pin order
    pin_names = {}
    for l in lines:
        if not l.startswith(".subckt "):
            continue
        sl = [x for x in l.split(' ') if x]
        pin_names[sl[1]] = [fix_brackets(x) for x in sl[2:]]
    des = Design()
    curr_mod = None
    # Do the actual import
    for l in lines:
        sl = [x for x in l.split(' ') if x]
        if l.startswith(".subckt "):
            mod_name = sl[1]
            if (mod_name in lib.modules and lib.modules[mod_name].blackbox) or mod_name in extra_boxes:
                curr_mod = None # don't import content of blackboxes
            else:
                curr_mod = Module(name=fix_modname(mod_name))
                for pin_name in pin_names[mod_name]:
                    if mod_name in lib.modules and pin_name in lib.modules[mod_name].pins:
                        curr_mod.ports[pin_name] = ModulePort(name=pin_name, direction=lib.modules[mod_name].get_dir(pin_name), net=pin_name)
                    else:
                        curr_mod.ports[pin_name] = ModulePort(name=pin_name, direction=PortDir.UNKNOWN, net=pin_name)
        elif l.startswith(".ends"):
            if curr_mod is not None:
                des.modules[curr_mod.name] = curr_mod
            curr_mod = None
        elif l.startswith("."): # .option etc
            continue
        else:
            if len(sl) >= 2 and curr_mod is not None:
                inst = CellInst(name=sl[0], cell_type=sl[-1])
                for pin_name, net in zip(pin_names[inst.cell_type], sl[1:-1]):
                    # TODO: some power pins don't end up as proper pins...
                    if pin_name.endswith('#') and (net.endswith(local_power) or net.startswith(local_ground) or net == "SUB"):
                        continue
                    inst.ports[pin_name] = fix_brackets(net)
                curr_mod.insts[inst.name] = inst
    return des

def fold_buffers(mod):
    # Eliminate buffers from the netlist, moving users of their outputs to the input net
    # and then deleting those instances. This is because PnR might have inserted extra buffers
    # on clock trees, high-fanout nets, etc
    to_delete = set()
    for inst in mod.insts.values():
        if inst.cell_type not in buffers:
            continue
        i = inst.ports[buffer_ports[0]]
        q = inst.ports[buffer_ports[1]]
        if q == local_ground:
            continue
        i_data = mod.nets[i]
        q_data = mod.nets[q]
        for user in q_data.users:
            mod.insts[user.inst].ports[user.port] = i
            i_data.users.add(user)
            i_data.buffer_depth[user] = i_data.buffer_depth.get(InstPortRef(inst.name, buffer_ports[0]), 0) + \
                q_data.buffer_depth.get(user, 0) + 1
        for port_data in mod.ports.values():
            if port_data.net == q: port_data.net = i
        q_data.driver = None
        q_data.users = set()
        to_delete.add(inst.name)

    buffer_count = len(to_delete)
    for buf in to_delete:
        del mod.insts[buf]
    return buffer_count

def run_lvs(synth_des, pnr_des, top):
    synth_mod = synth_des.modules[top]
    pnr_mod = pnr_des.modules[top]
    work_queue = []
    equiv_map = {}
    error_count = 0
    equiv_count = 0

    def err(s):
        nonlocal error_count
        print(s, file=sys.stderr)
        error_count += 1

    def do_enqueue(synth_net, pnr_net):
        if pnr_net in equiv_map:
            if synth_net != equiv_map[pnr_net]:
                err(f"previously determined {pnr_net} -> {equiv_map[pnr_net]} but now attempting to check equivalence with {synth_net}")
        else:
            equiv_map[pnr_net] = synth_net
            work_queue.append((synth_net, pnr_net))
    top_level_inputs = dict()
    for port, port_data in synth_mod.ports.items():
        if port not in pnr_mod.ports:
            if port in pnr_mod.nets:
                err(f"port {port} missing from pnr design but added based on net")
                port_data = ModulePort(name=port, direction=port_data.direction, net=port)
                pnr_mod.ports[port] = port_data
            else:
                err(f"port {port} missing from pnr design")
                continue
        do_enqueue(port_data.net, pnr_mod.ports[port].net)
        if port_data.direction == PortDir.INPUT: top_level_inputs[port_data.net] = port
    while len(work_queue) > 0:
        synth_netname, pnr_netname = work_queue.pop()
        synth_net = synth_mod.nets[synth_netname]
        pnr_net = pnr_mod.nets[pnr_netname]
        if synth_net.driver is None:
            # TODO: constants, power
            if pnr_net.driver is not None:
                pnr_driver = pnr_mod.insts[pnr_net.driver.inst]
                if synth_netname == "$const0" and pnr_driver.cell_type in const_zeros:
                    equiv_count += 1
                    continue
                if synth_netname == "$const1" and pnr_driver.cell_type in const_ones:
                    equiv_count += 1
                    continue
                err(f"net {pnr_netname} ({synth_netname}) driven in pnr design by {pnr_net.driver} but not in synth design")
            elif synth_netname in top_level_inputs:
                if top_level_inputs[synth_netname] != pnr_netname:
                    err(f"expected top level input {top_level_inputs[synth_netname]} ({synth_netname}) on pnr net {pnr_netname}")
            continue
        if pnr_net.driver is None:
            err(f"net {pnr_netname} ({synth_netname}) undriven in pnr design")
            continue

        synth_driver = synth_mod.insts[synth_net.driver.inst]
        pnr_driver = pnr_mod.insts[pnr_net.driver.inst]
        if (synth_driver.cell_type, synth_net.driver.port) != (pnr_driver.cell_type, pnr_net.driver.port):
            err(f"driver mismatch: synth {synth_netname} {synth_driver.cell_type}.{synth_net.driver.port} pnr {pnr_netname} {pnr_driver.cell_type}.{pnr_net.driver.port}")
            continue
        for port_name, synth_port_net in synth_driver.ports.items():
            if port_name == synth_net.driver.port:
                continue
            assert port_name in pnr_driver.ports, f"port {port} missing from pnr cell {pnr_driver.name}"
            do_enqueue(synth_port_net, pnr_driver.ports[port_name])
        equiv_count += 1
    return (error_count, equiv_count)

def check_clock_skew(pnr_des, top):
    # This checks for the most serious cases of clock skew by ensuring all clock nets are driven by the same number of cascaded buffers,
    # in lieu of having proper pex and timing set up
    pnr_mod = pnr_des.modules[top]
    clock_depth = dict()

    error_count = 0

    def err(s):
        nonlocal error_count
        print(s, file=sys.stderr)
        error_count += 1

    for inst_data in pnr_mod.insts.values():
        if inst_data.cell_type not in dffs: continue
        clock_net = pnr_mod.nets[inst_data.ports[dff_clk]]
        depth = clock_net.buffer_depth.get(InstPortRef(inst_data.name, dff_clk), 0)
        if clock_net.name not in clock_depth:
            clock_depth[clock_net.name] = depth
        elif clock_depth[clock_net.name] != depth:
            err(f"buffer depth mismatch for {clock_net.name}: {depth} on {inst_data.name} vs {clock_depth[clock_net.name]}")
    for clk, depth in clock_depth.items():
        print(f"buffer depth for clock {clk}: {depth}")
    return error_count

def main():
    if len(sys.argv) < 3:
        print("Usage: netlist_compare.py synth_design.json lvs_design.spice [out_design.json]")
        assert False
    with open(sys.argv[1], "r") as jsonf:
        synth_des = import_yosys_json(jsonf)
    top_level = None
    for mod in synth_des.modules.values():
        if not mod.blackbox:
            assert top_level is None, f"multiple top modules found {top_level} and {mod.name}"
            top_level = mod.name
        mod.link(synth_des)
    assert top_level is not None, f"no top level module found in input JSON"

    with open(sys.argv[2], "r") as spicef:
        pnr_des = import_spice(synth_des, spicef)
    error_count = 0
    # for mod in pnr_des.modules.values():
    #     if mod.name in synth_des.modules:
    #         error_count += mod.link(synth_des)
    pnr_des.rename_module("corona_cts", top_level)
    pnr_top = pnr_des.modules[top_level]
    pnr_top.flatten(pnr_des)
    error_count += pnr_top.link(synth_des)

    fold_buffers(synth_des.modules[top_level])
    buffer_count = fold_buffers(pnr_des.modules[top_level])
    print(f"eliminated {buffer_count} buffers in PnR design")

    lvs_error_count, equiv_count = run_lvs(synth_des, pnr_des, top_level)
    error_count += lvs_error_count
    error_count += check_clock_skew(pnr_des, top_level)
    print(f"{error_count} errors, {equiv_count} nets deemed equivalent")

    if len(sys.argv) >= 4:
        with open(sys.argv[3], "w") as out_jsonf:
            pnr_des.modules[top_level].write_json(synth_des, out_jsonf)

    if error_count > 0:
        sys.exit(1)

if __name__ == '__main__':
    main()