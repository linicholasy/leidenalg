LIBLEIDENALG_BRANCH=relative-pop-penalty
LIBLEIDENALG_REPO=https://github.com/linicholasy/libleidenalg.git

ROOT_DIR=`pwd`
echo "Using root dir ${ROOT_DIR}"

# Create source directory
if [ ! -d "${ROOT_DIR}/build-deps/src" ]; then
  echo ""
  echo "Make directory ${ROOT_DIR}/build-deps/src"
  mkdir -p ${ROOT_DIR}/build-deps/src
fi

cd ${ROOT_DIR}/build-deps/src
if [ ! -d "libleidenalg" ]; then
  echo ""
  echo "Cloning libleidenalg (${LIBLEIDENALG_BRANCH}) into ${ROOT_DIR}/build-deps/src/libleidenalg"
  git clone --branch ${LIBLEIDENALG_BRANCH} ${LIBLEIDENALG_REPO} --single-branch
fi

# Make sure the git repository points to the correct branch
echo ""
echo "Checking out ${LIBLEIDENALG_BRANCH} in ${ROOT_DIR}/build-deps/src/libleidenalg"
cd ${ROOT_DIR}/build-deps/src/libleidenalg
git fetch origin ${LIBLEIDENALG_BRANCH}
git checkout ${LIBLEIDENALG_BRANCH}

# Provide a VERSION file so cmake can determine the version without git tags
if [ ! -f "VERSION" ]; then
  echo "0.1.0" > VERSION
fi

# Make build directory
if [ ! -d "${ROOT_DIR}/build-deps/build/libleidenalg" ]; then
  echo ""
  echo "Make directory ${ROOT_DIR}/build-deps/build/libleidenalg"
  mkdir -p ${ROOT_DIR}/build-deps/build/libleidenalg
fi

# Configure, build and install
cd ${ROOT_DIR}/build-deps/build/libleidenalg

echo ""
echo "Configure libleidenalg build"
cmake ${ROOT_DIR}/build-deps/src/libleidenalg \
    -DCMAKE_INSTALL_PREFIX=${ROOT_DIR}/build-deps/install/ \
    -DBUILD_SHARED_LIBS=ON \
    -Digraph_ROOT=${ROOT_DIR}/build-deps/install/lib/cmake/igraph/ \
    ${EXTRA_CMAKE_ARGS}

echo ""
echo "Build libleidenalg"
cmake --build . --config Release

echo ""
echo "Install libleidenalg to ${ROOT_DIR}/build-deps/install/"
cmake --build . --target install --config Release
