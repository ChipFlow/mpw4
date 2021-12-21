function install_pydeps {
	pip install git+https://github.com/amaranth-lang/amaranth
	pip install git+https://github.com/amaranth-lang/amaranth-stdio
	pip install klayout
}

function do_build {
	export CORIOLIS_TOP=/home/runner/coriolis-2.x/Linux.x86_64/Release.Shared/install
	export LD_LIBRARY_PATH=$CORIOLIS_TOP/lib64
	export PYTHONPATH=$PYTHONPATH:$CORIOLIS_TOP/lib64/python3/dist-packages:$CORIOLIS_TOP/lib64/python3/dist-packages/crlcore:$CORIOLIS_TOP/lib64/python3/dist-packages/cumulus/
	export PATH="$GITHUB_WORKSPACE/.yosys/usr/local/bin:$PATH"
	python3 -m soc.sky130 --synth --pnr
}

