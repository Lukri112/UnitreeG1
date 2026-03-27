#!/bin/bash
echo "Setup unitree ros2 default environment"
source /opt/ros/foxy/setup.bash
source $HOME/unitree_ros2/cyclonedds_ws/install/setup.bash
export RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
export CYCLONEDDS_HOME=$HOME/unitree_ros2/cyclonedds_ws/install
export CMAKE_PREFIX_PATH=$HOME/unitree_ros2/cyclonedds_ws/install:$CMAKE_PREFIX_PATH
unset CYCLONEDDS_URI
