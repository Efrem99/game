#!/bin/bash
echo "[XBot RPG Ultimate] Building C++ Core..."

BUILD_DIR="build-cpp"
mkdir -p $BUILD_DIR
cd $BUILD_DIR

# Check for pybind11
if ! python3 -m pybind11 --version &> /dev/null; then
    echo "Installing pybind11..."
    python3 -m pip install pybind11 --quiet
fi

# Configure and Build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc 2>/dev/null || echo 4)

if [ $? -eq 0 ]; then
    echo "[SUCCESS] Build complete."
else
    echo "[ERROR] Build failed!"
    exit 1
fi

cd ..
