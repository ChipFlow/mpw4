drc off

gds read build/sky130/user_project_wrapper_fixedup.gds

cd build/sky130
shell mkdir -p extracted
cd extracted

load user_project_wrapper
extract unique all
extract no resistance
extract no length
extract no capacitance
extract no coupling
extract no adjust
extract

ext2spice hierarchy on
ext2spice subcircuit descend on
ext2spice user_project_wrapper

puts "SPICE extraction done"

antennacheck debug
antennacheck

puts "antenna check done"

quit -noprompt

