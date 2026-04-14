cmake_minimum_required(VERSION 3.10)
project(xbot_rpg_ultimate CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find pybind11
find_package(Python3 REQUIRED COMPONENTS Development Interpreter)

# Source files
set(CPP_SOURCES
    cpp/src/AnimationBlender.cpp
    cpp/src/AttentionManager.cpp
    cpp/src/CombatSystem.cpp
    cpp/src/EnemyRuntimeSystem.cpp
    cpp/src/MagicSystem.cpp
    cpp/src/NpcRuntimeSystem.cpp
    cpp/src/ParkourSystem.cpp
    cpp/src/ParticleSystem.cpp
    cpp/src/PhysicsEngine.cpp
    cpp/src/PyBindings.cpp
    cpp/src/WaterSimulation.cpp
)

# Panda3D paths (These might need adjustment based on the user's installation)
# We'll allow overriding these via command line
if(NOT PANDA_INCLUDE_DIR)
    set(PANDA_INCLUDE_DIR "C:/Panda3D-1.10.14-x64/include")
endif()
if(NOT PANDA_LIB_DIR)
    set(PANDA_LIB_DIR "C:/Panda3D-1.10.14-x64/lib")
endif()

# Important: Panda3D needs some specific flags or includes sometimes
# but with pybind11 we usually just need the headers for the Python version

# Create the pybind11 module
# Note: we need to find pybind11 first.
# Usually 'pip install pybind11' is enough and find_package works if CMAKE_PREFIX_PATH is set
# or we can use the python module itself to find it.
execute_process(
    COMMAND "${Python3_EXECUTABLE}" -m pybind11 --includes
    OUTPUT_VARIABLE PYBIND11_INCLUDES
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

add_library(game_core MODULE ${CPP_SOURCES})

target_include_directories(game_core PRIVATE
    cpp/include
    ${Python3_INCLUDE_DIRS}
    ${PANDA_INCLUDE_DIR}
)

if(TARGET Python3::Module)
    target_link_libraries(game_core PRIVATE Python3::Module)
else()
    target_link_libraries(game_core PRIVATE ${Python3_LIBRARIES})
endif()

# If the user has pybind11 headers in a weird spot, we add them
string(REPLACE "-I" "" PYBIND11_INCLUDES_CLEAN "${PYBIND11_INCLUDES}")
separate_arguments(PYBIND11_INCLUDES_LIST WINDOWS_COMMAND "${PYBIND11_INCLUDES_CLEAN}")
target_include_directories(game_core PRIVATE ${PYBIND11_INCLUDES_LIST})

set_target_properties(game_core PROPERTIES
    PREFIX ""
    SUFFIX ".pyd"
    LIBRARY_OUTPUT_DIRECTORY "${CMAKE_SOURCE_DIR}"
)

# Link against Panda3D if needed (usually only if using Panda C++ APIs)
# target_link_libraries(game_core PRIVATE ${PANDA_LIB_DIR}/libp3framework.lib ...)
