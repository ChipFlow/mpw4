# Install latest Yosys
function build_yosys {
    DESTDIR=`pwd`/.yosys
    pushd yosys
    make -j`nproc`
    sudo make install DESTDIR=$DESTDIR
    popd
}

# Install latest Coriolis
function build_coriolis {
    pushd ${HOME}/coriolis-2.x/src/coriolis
    ./bootstrap/ccb.py --project=coriolis --qt5 --make="-j`nproc` install"
    popd
}
