// Copyright (c) 2025, Unitree Robotics Co., Ltd.
// All rights reserved.

#pragma once

#include "isaaclab/envs/manager_based_rl_env.h"

#include <algorithm>
#include <array>
#include <chrono>
#include <cmath>
#include <cstring>
#include <iostream>

#include <sys/socket.h>
#include <netinet/in.h>
#include <unistd.h>
#include <fcntl.h>

namespace isaaclab
{
namespace mdp
{

REGISTER_OBSERVATION(base_ang_vel)
{
    auto & asset = env->robot;
    auto & data = asset->data.root_ang_vel_b;
    return std::vector<float>(data.data(), data.data() + data.size());
}

REGISTER_OBSERVATION(projected_gravity)
{
    auto & asset = env->robot;
    auto & data = asset->data.projected_gravity_b;
    return std::vector<float>(data.data(), data.data() + data.size());
}

REGISTER_OBSERVATION(joint_pos)
{
    auto & asset = env->robot;
    std::vector<float> data;

    std::vector<int> joint_ids;
    try {
        joint_ids = params["asset_cfg"]["joint_ids"].as<std::vector<int>>();
    } catch(const std::exception& e) {
    }

    if(joint_ids.empty())
    {
        data.resize(asset->data.joint_pos.size());
        for(size_t i = 0; i < asset->data.joint_pos.size(); ++i)
        {
            data[i] = asset->data.joint_pos[i];
        }
    }
    else
    {
        data.resize(joint_ids.size());
        for(size_t i = 0; i < joint_ids.size(); ++i)
        {
            data[i] = asset->data.joint_pos[joint_ids[i]];
        }
    }

    return data;
}

REGISTER_OBSERVATION(joint_pos_rel)
{
    auto & asset = env->robot;
    std::vector<float> data;

    data.resize(asset->data.joint_pos.size());
    for(size_t i = 0; i < asset->data.joint_pos.size(); ++i) {
        data[i] = asset->data.joint_pos[i] - asset->data.default_joint_pos[i];
    }

    try {
        std::vector<int> joint_ids;
        joint_ids = params["asset_cfg"]["joint_ids"].as<std::vector<int>>();
        if(!joint_ids.empty()) {
            std::vector<float> tmp_data;
            tmp_data.resize(joint_ids.size());
            for(size_t i = 0; i < joint_ids.size(); ++i){
                tmp_data[i] = data[joint_ids[i]];
            }
            data = tmp_data;
        }
    } catch(const std::exception& e) {
    }

    return data;
}

REGISTER_OBSERVATION(joint_vel_rel)
{
    auto & asset = env->robot;
    auto data = asset->data.joint_vel;

    try {
        const std::vector<int> joint_ids = params["asset_cfg"]["joint_ids"].as<std::vector<int>>();

        if(!joint_ids.empty()) {
            data.resize(joint_ids.size());
            for(size_t i = 0; i < joint_ids.size(); ++i) {
                data[i] = asset->data.joint_vel[joint_ids[i]];
            }
        }
    } catch(const std::exception& e) {
    }
    return std::vector<float>(data.data(), data.data() + data.size());
}

REGISTER_OBSERVATION(last_action)
{
    auto data = env->action_manager->action();
    return std::vector<float>(data.data(), data.data() + data.size());
};

REGISTER_OBSERVATION(velocity_commands)
{
    std::vector<float> obs(3);

    const auto cfg = env->cfg["commands"]["base_velocity"]["ranges"];

    // ------------------------------------------------------------------
    // UDP override for reproducible velocity experiments.
    //
    // UDP packet format:
    //   3 float32 values: [vx, vy, yaw_rate]
    //
    // UDP port:
    //   5005
    //
    // Behavior:
    //   fresh UDP packet <= 0.5 s old  -> use UDP command
    //   no fresh UDP packet            -> use original joystick behavior
    // ------------------------------------------------------------------

    static bool udp_initialized = false;
    static int udp_sockfd = -1;
    static std::array<float, 3> udp_cmd = {0.0f, 0.0f, 0.0f};
    static auto last_udp_time = std::chrono::steady_clock::time_point::min();

    constexpr int UDP_CMD_PORT = 5005;
    constexpr double UDP_CMD_TIMEOUT_S = 0.5;

    if (!udp_initialized)
    {
        udp_initialized = true;

        udp_sockfd = socket(AF_INET, SOCK_DGRAM, 0);

        if (udp_sockfd >= 0)
        {
            int reuse = 1;
            setsockopt(udp_sockfd, SOL_SOCKET, SO_REUSEADDR, &reuse, sizeof(reuse));

            sockaddr_in addr;
            std::memset(&addr, 0, sizeof(addr));
            addr.sin_family = AF_INET;
            addr.sin_addr.s_addr = INADDR_ANY;
            addr.sin_port = htons(UDP_CMD_PORT);

            if (bind(udp_sockfd, reinterpret_cast<sockaddr*>(&addr), sizeof(addr)) < 0)
            {
                std::cerr << "[velocity_commands] UDP bind failed on port "
                          << UDP_CMD_PORT
                          << ". Falling back to joystick only."
                          << std::endl;

                close(udp_sockfd);
                udp_sockfd = -1;
            }
            else
            {
                int flags = fcntl(udp_sockfd, F_GETFL, 0);
                if (flags >= 0)
                {
                    fcntl(udp_sockfd, F_SETFL, flags | O_NONBLOCK);
                }

                std::cout << "[velocity_commands] UDP override listening on port "
                          << UDP_CMD_PORT
                          << std::endl;
            }
        }
        else
        {
            std::cerr << "[velocity_commands] Could not create UDP socket. "
                      << "Falling back to joystick only."
                      << std::endl;
        }
    }

    // Read all available UDP packets and keep the newest one.
    if (udp_sockfd >= 0)
    {
        while (true)
        {
            float buffer[3] = {0.0f, 0.0f, 0.0f};

            ssize_t n = recvfrom(
                udp_sockfd,
                buffer,
                sizeof(buffer),
                MSG_DONTWAIT,
                nullptr,
                nullptr
            );

            if (n == static_cast<ssize_t>(sizeof(buffer)))
            {
                udp_cmd[0] = buffer[0];
                udp_cmd[1] = buffer[1];
                udp_cmd[2] = buffer[2];

                last_udp_time = std::chrono::steady_clock::now();
            }
            else
            {
                break;
            }
        }
    }

    auto now = std::chrono::steady_clock::now();
    double udp_age_s = 999.0;

    if (last_udp_time != std::chrono::steady_clock::time_point::min())
    {
        udp_age_s = std::chrono::duration<double>(now - last_udp_time).count();
    }

    // 1. Fresh UDP command has priority.
    if (udp_age_s <= UDP_CMD_TIMEOUT_S)
    {
        obs[0] = std::clamp(
            udp_cmd[0],
            cfg["lin_vel_x"][0].as<float>(),
            cfg["lin_vel_x"][1].as<float>()
        );

        obs[1] = std::clamp(
            udp_cmd[1],
            cfg["lin_vel_y"][0].as<float>(),
            cfg["lin_vel_y"][1].as<float>()
        );

        obs[2] = std::clamp(
            udp_cmd[2],
            cfg["ang_vel_z"][0].as<float>(),
            cfg["ang_vel_z"][1].as<float>()
        );

        return obs;
    }

    // 2. Original Unitree/MJLab behavior.
    auto & joystick = env->robot->data.joystick;

    obs[0] = std::clamp(
        joystick->ly(),
        cfg["lin_vel_x"][0].as<float>(),
        cfg["lin_vel_x"][1].as<float>()
    );

    obs[1] = std::clamp(
        -joystick->lx(),
        cfg["lin_vel_y"][0].as<float>(),
        cfg["lin_vel_y"][1].as<float>()
    );

    obs[2] = std::clamp(
        -joystick->rx(),
        cfg["ang_vel_z"][0].as<float>(),
        cfg["ang_vel_z"][1].as<float>()
    );

    return obs;
}

REGISTER_OBSERVATION(gait_phase)
{
    float period = params["period"].as<float>();
    float delta_phase = env->step_dt * (1.0f / period);

    env->global_phase += delta_phase;
    env->global_phase = std::fmod(env->global_phase, 1.0f);

    auto cmd = isaaclab::mdp::velocity_commands(env, params);
    float cmd_norm = std::sqrt(
        cmd[0] * cmd[0] +
        cmd[1] * cmd[1] +
        cmd[2] * cmd[2]
    );

    std::vector<float> obs(2);
    obs[0] = std::sin(env->global_phase * 2 * M_PI);
    obs[1] = std::cos(env->global_phase * 2 * M_PI);

    if (cmd_norm < 0.1f)
    {
        obs[0] = 0.0f;
        obs[1] = 0.0f;
    }

    return obs;
}

}
}
