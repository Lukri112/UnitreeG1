# Unitree G1

Dieses Repository dient als Ausgangspunkt für Inhalte, Code und Notizen rund um den **Unitree G1 Edu+**.

Der **Unitree G1 Edu+** ist ein humanoider Forschungs- und Entwicklungsroboter von Unitree Robotics. Er ist für Anwendungen in Forschung, Embodied AI, Bewegungssteuerung, Mensch-Roboter-Interaktion sowie algorithmische Entwicklung im Bereich humanoider Robotik interessant.

## Offizielle Ressourcen

- Unitree Robotics GitHub: <https://github.com/unitreerobotics>

## Hinweis

Dieses Repository ist aktuell bewusst schlank gehalten und kann später um Dokumentation, Setup-Anleitungen, SDK-Hinweise, Experimente oder Beispielcode erweitert werden.  
### Hilfreiche Docker Befehle: 
    
    docker start ros2_foxy_dev
    docker exec -it ros2_foxy_dev bash
    docker ps -a
    docker rm -f ros2_foxy_dev

Achtung!! Vor jedem neuen Container start prüfen, ob der Container Zugriff auf den Display Adapter hat:

    xhost +SI:localuser:root
    echo $DISPLAY
    xhost

Dann innerhalb des Docker containers folgende Zeilen ausführen um zu prüfen, ob das gleiche Display gefunden wird:

    echo $DISPLAY
    ls /tmp/.X11-unix

Falls der vom Container erstellte unitree_ws gesperrt ist für den User (Dateien kopieren) - Außerhalb des Containers ausführen:

    
    sudo chown -R $USER:$USER ~/unitree_ws
    chmod -R u+rwX ~/unitree_ws

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
    apt install -y mesa-utils
    alias ls='/bin/ls --color=auto'
    alias ll='/bin/ls -alF'
    #Check ob NVIDIA Treiber funktionieren
    glxinfo | grep "OpenGL renderer"
    glxinfo | grep "OpenGL vendor"
    
  5. Run unitree_full_setup.py

    python3 unitree_full_setup.py

### Next steps Ubuntu 20.04 / 22.04 / 24.04:
  
  1. Install all packages in the following order :

    rm -rf unitree_sdk2
    git clone https://github.com/unitreerobotics/unitree_sdk2
    cd ~/unitree_sdk2
    mkdir -p build
    cd build
    cmake .. -DCMAKE_INSTALL_PREFIX=/opt/unitree_robotics 
    sudo make install

    rm -rf unitree_sdk2_python
    git clone https://github.com/unitreerobotics/unitree_sdk2_python
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

Achtung!! Jeder PC kann ein anderes Network Interface (Ethernet / Wlan Adapter) haben, deshalb bitte prüfen:

    ip a

Dann überprüfen, welches Network Interface im CyclondeDDS setup verwendet wird und falls nötig im setup.sh ändern  
(enp5s0, eth1, enp2s0..):

    grep CYCLONEDDS_URI ~/unitree_ros2/setup.sh

Nach jeder Änderung im setup.sh, oder bei jedem neuen Terminal Aufruf / neuer Container:

    source /opt/ros/foxy/setup.bash
    source ~/unitree_ros2/cyclonedds_ws/install/setup.bash
    source ~/unitree_ros2/setup.sh


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

4. Build Deploy G1-Controller (29DOF):

       cd deploy/robots/g1
       mkdir build
       cd build
       cmake .. && make

       export LD_LIBRARY_PATH=$HOME/unitree_ros2/cyclonedds_ws/install/lib:$LD_LIBRARY_PATH
       export LD_LIBRARY_PATH=/usr/local/lib:$LD_LIBRARY_PATH

6. Start G1-Controller (29DOF):

        cd ~/unitree_rl_mjlab/deploy/robots/g1/build
   
       # Simulation Network Interface
        ./g1_ctrl --network lo 

        # Real Robot Network Interface
        ./g1_ctrl --network enp5s0

### Unitree MUJOCO:
    
 1. Install Dependencies:

        cd ~
        sudo apt install libyaml-cpp-dev libspdlog-dev libboost-all-dev libglfw3-dev
    
 2. Install and compile Mujoco (Docker Container Version root):

        apt update
        apt install -y \
        git cmake build-essential \
        libglfw3-dev libglew-dev libxinerama-dev libxcursor-dev libxi-dev \
        libxrandr-dev libxxf86vm-dev libx11-dev libxext-dev libxrender-dev \
        libxkbcommon-dev patchelf

        mkdir -p /root/.mujoco
        cd /root/.mujoco
        # MuJoCo 3.3.6 Source holen
        git clone --branch 3.3.6 --depth 1 https://github.com/google-deepmind/mujoco.git mujoco-3.3.6

        # MuJoCo 3.3.6 bauen
        cd /root/.mujoco/mujoco-3.3.6  
        mkdir -p build
        cd build
        export CC=/usr/bin/gcc
        export CXX=/usr/bin/g++
        export CXXFLAGS="-std=c++17"
        export CFLAGS="-O2"

        cmake .. \
          -DCMAKE_BUILD_TYPE=Release \
          -DCMAKE_CXX_STANDARD=17 \
          -DCMAKE_CXX_STANDARD_REQUIRED=ON \
          -DCMAKE_CXX_EXTENSIONS=OFF \
          -DABSL_PROPAGATE_CXX_STD=ON
        make -j"$(nproc)"

        #Bei jedem neuen Container start werden diese export Befehle benötigt!!!

        export LD_LIBRARY_PATH=/root/.mujoco/mujoco-3.3.6/build/lib:/root/.mujoco/mujoco-3.3.6/lib:$LD_LIBRARY_PATH    
        export LIBRARY_PATH=/root/.mujoco/mujoco-3.3.6/build/lib:/root/.mujoco/mujoco-3.3.6/lib:$LIBRARY_PATH
        export CPATH=/root/.mujoco/mujoco-3.3.6/include:/root/.mujoco/mujoco-3.3.6/simulate:$CPATH

        cd ~/unitree_mujoco/simulate/
        ln -s ~/.mujoco/mujoco-3.3.6 mujoco
        mkdir build 
        cd build
        cmake ..
        make -j4
    
4. Test Mujoco Simulator:

       ./unitree_mujoco


### Unitree ISAACLAB:
Isaac Lab wird aufgrund der größeren Sim2Real Gap zurzeit nur als zweiter Controller verwendet.
Sollte in Zukunft das Framework besser werden als Mjlab & Mujoco, wird Isaac Lab näher behandelt.

    # Compile the robot_controller
    cd ~/unitree_rl_lab/deploy/robots/g1_29dof # or other robots
    mkdir build
    cd build
    cmake .. && make

Roboter Controller starten:
    
    cd ~/unitree_rl_lab/deploy/robots/g1_29dof
    
    # Simulation Network Interface
    ./g1_ctrl --network lo 

    # Real Robot Network Interface
    ./g1_ctrl --network enp5s0
