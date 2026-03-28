# Unitree G1

Dieses Repository dient als Ausgangspunkt für Inhalte, Code und Notizen rund um den **Unitree G1 Edu+**.

Der **Unitree G1 Edu+** ist ein humanoider Forschungs- und Entwicklungsroboter von Unitree Robotics. Er ist für Anwendungen in Forschung, Embodied AI, Bewegungssteuerung, Mensch-Roboter-Interaktion sowie algorithmische Entwicklung im Bereich humanoider Robotik interessant.

## Offizielle Ressourcen

- Unitree Robotics GitHub: <https://github.com/unitreerobotics>

## Hinweis

Dieses Repository ist aktuell bewusst schlank gehalten und kann später um Dokumentation, Setup-Anleitungen, SDK-Hinweise, Experimente oder Beispielcode erweitert werden.
Hilfreiche Docker Befehle: 
    
    docker exec -it ros2_foxy_dev bash
    docker ps -a
    docker rm -f ros2_foxy_dev

## Setup

### Ubuntu 20.04:
  
  1. Download and run unitree_full_setup.py  

    apt update
    apt upgrade
    apt install -y python3-pip sudo iproute2 git cmake
    python3 unitree_full_setup.py

### Ubuntu 22.04 / 24.04:
  1. Download unitree_full_setup.py  
  2. Download and run ros2_foxy_docker_setup.sh  
  3. Inside the Docker Containe change to Downloads    
  
    cd root/Downloads
    
  4. Install necessary tools 
  
    apt update
    apt upgrade
    apt install -y python3-pip sudo iproute2 git cmake
    
  5. Run unitree_full_setup.py

    python3 unitree_full_setup.py

### Next steps Ubuntu 20.04 / 22.04 / 24.04:
  
  1. Install all packages in the following order :

    cd ~/unitree_sdk2
    mkdir -p build && cd build
    cmake .. -DCMAKE_INSTALL_PREFIX=/opt/unitree_robotics 
    make -j"$(nproc)"
    sudo make install

    cd ~/unitree_sdk2_python
    export CYCLONEDDS_HOME=~/unitree_ros2/cyclonedds_ws/install
    pip3 install -e .
    
  2. Test C++ Example Code:

    cd ~/unitree_sdk2
    find . -type f -executable
     
  3. Test Python Example Code:

    cd ~/unitree_sdk2_python/example/g1/audio 
    python3 g1_audio_client_example.py enp5s0

  4. Test ROS2 Example Code (Simulation):

    cd ~/unitree_ros2
    source /opt/ros/foxy/setup.bash
    source ~/unitree_ros2/cyclonedds_ws/install/setup.bash
    source ~/unitree_ros2/setup_local.sh
    cd ~/unitree_ros2/example
    colcon build
    source install/setup.bash
    ./install/unitree_ros2_example/bin/read_motion_state

  5. Test ROS2 Example Code (Realer Roboter):

    cd ~/unitree_ros2
    source /opt/ros/foxy/setup.bash
    source ~/unitree_ros2/cyclonedds_ws/install/setup.bash
    source ~/unitree_ros2/setup.sh
    cd ~/unitree_ros2/example
    colcon build
    source install/setup.bash
    ./install/unitree_ros2_example/bin/read_motion_state

  6. Einzelne Projektordner clonen:

    cd ~
    git clone --filter=blob:none --no-checkout https://github.com/Lukri112/UnitreeG1.git
    cd ~/UnitreeG1
    git sparse-checkout init --cone
    git sparse-checkout set unitree_rl_mjlab unitree_rl_lab unitree_mujoco
    git checkout main

    mv ~/UnitreeG1/unitree_rl_mjlab ~/
    mv ~/UnitreeG1/unitree_rl_lab ~/
    mv ~/UnitreeG1/unitree_mujoco ~/
    cd ~
    rm -rf ~/UnitreeG1

### Unitree MJLAB:


  1. Wie im Unitree Github beschrieben das setup durchführen:

    apt update
    apt install -y wget

  2. Download and Install MiniConda -- alternative with venv and deadsnakes Python 3.11

    mkdir -p ~/miniconda3
    wget https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O ~/miniconda3/miniconda.sh
    bash ~/miniconda3/miniconda.sh -b -u -p ~/miniconda3
    rm ~/miniconda3/miniconda.sh
    
    ~/miniconda3/bin/conda init --all
    source ~/.bashrc
    
    conda create -n env_unitree_mjlab python=3.11
    conda activate env_unitree_mjlab
    
  3. Install Dependencies:

    cd ~/unitree_rl_mjlab
    sudo apt install -y libyaml-cpp-dev libboost-all-dev libeigen3-dev libspdlog-dev libfmt-dev
    cd unitree_rl_mjlab
    pip install -e .

### Unitree MUJOCO:
    
 1. Install Dependencies:

        sudo apt install libyaml-cpp-dev libspdlog-dev libboost-all-dev libglfw3-dev
    
 2. Install and compile Mujoco:
    
        cd unitree_mujoco/simulate/
        ln -s ~/.mujoco/mujoco-3.3.6 mujoco
        mkdir build && cd build
        cmake ..
        make -j4
    
3. Test Mujoco Simulator:

       ./unitree_mujoco -r go2 -s scene_terrain.xml
