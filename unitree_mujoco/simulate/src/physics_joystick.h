#pragma once

#include <iostream>
#include <memory>
#include <mutex>
#include <string>

#include <GLFW/glfw3.h>
#include <unitree/dds_wrapper/common/unitree_joystick.hpp>

#include "joystick/joystick.h"

namespace unitree_mujoco_keyboard
{
struct KeyboardState
{
    double lx = 0.0;
    double ly = 0.0;
    double rx = 0.0;
    double ry = 0.0;
    bool back = false;
    bool start = false;
    bool lb = false;
    bool rb = false;
    bool a = false;
    bool b = false;
    bool x = false;
    bool y = false;
    bool up = false;
    bool down = false;
    bool left = false;
    bool right = false;
    bool lt = false;
    bool rt = false;
};

inline std::mutex &keyboardMutex()
{
    static std::mutex m;
    return m;
}

inline KeyboardState &keyboardState()
{
    static KeyboardState s;
    return s;
}

inline void resetKeyboardStateLocked(KeyboardState &s)
{
    s.lx = 0.0;
    s.ly = 0.0;
    s.rx = 0.0;
    s.ry = 0.0;
    s.back = false;
    s.start = false;
    s.lb = false;
    s.rb = false;
    s.a = false;
    s.b = false;
    s.x = false;
    s.y = false;
    s.up = false;
    s.down = false;
    s.left = false;
    s.right = false;
    s.lt = false;
    s.rt = false;
}

inline void resetKeyboardState()
{
    std::lock_guard<std::mutex> lock(keyboardMutex());
    resetKeyboardStateLocked(keyboardState());
}

inline void handleKeyboardTeleopKey(int key, int action)
{
    std::lock_guard<std::mutex> lock(keyboardMutex());
    auto &s = keyboardState();

    const bool pressed = (action == GLFW_PRESS || action == GLFW_REPEAT);
    const bool released = (action == GLFW_RELEASE);

    if (pressed && key == GLFW_KEY_SPACE)
    {
        resetKeyboardStateLocked(s);
        return;
    }

    if (!(pressed || released))
    {
        return;
    }

    switch (key)
    {
    case GLFW_KEY_W:
        s.ly = pressed ? 1.0 : 0.0;
        break;
    case GLFW_KEY_S:
        s.ly = pressed ? -1.0 : 0.0;
        break;
    case GLFW_KEY_A:
        s.lx = pressed ? -1.0 : 0.0;
        break;
    case GLFW_KEY_D:
        s.lx = pressed ? 1.0 : 0.0;
        break;
    case GLFW_KEY_Q:
        s.rx = pressed ? -5.5 : 0.0;
        break;
    case GLFW_KEY_E:
        s.rx = pressed ? 5.5 : 0.0;
        break;
    case GLFW_KEY_R:
        s.ry = pressed ? 1.0 : 0.0;
        break;
    case GLFW_KEY_F:
        s.ry = pressed ? -1.0 : 0.0;
        break;
    case GLFW_KEY_ENTER:
        s.start = pressed;
        break;
    case GLFW_KEY_BACKSPACE:
        s.back = pressed;
        break;
    case GLFW_KEY_LEFT_SHIFT:
    case GLFW_KEY_RIGHT_SHIFT:
        s.lb = pressed;
        break;
    case GLFW_KEY_LEFT_CONTROL:
    case GLFW_KEY_RIGHT_CONTROL:
        s.rb = pressed;
        break;
    case GLFW_KEY_Z:
        s.a = pressed;
        break;
    case GLFW_KEY_X:
        s.b = pressed;
        break;
    case GLFW_KEY_C:
        s.x = pressed;
        break;
    case GLFW_KEY_V:
        s.y = pressed;
        break;
    case GLFW_KEY_UP:
        s.up = pressed;
        break;
    case GLFW_KEY_DOWN:
        s.down = pressed;
        break;
    case GLFW_KEY_LEFT:
        s.left = pressed;
        break;
    case GLFW_KEY_RIGHT:
        s.right = pressed;
        break;
    case GLFW_KEY_1:
        s.lt = pressed;
        break;
    case GLFW_KEY_2:
        s.rt = pressed;
        break;
    default:
        break;
    }
}

inline KeyboardState snapshotKeyboardState()
{
    std::lock_guard<std::mutex> lock(keyboardMutex());
    return keyboardState();
}
} // namespace unitree_mujoco_keyboard


class KeyboardJoystick : public unitree::common::UnitreeJoystick
{
public:
    KeyboardJoystick()
        : unitree::common::UnitreeJoystick()
    {
        unitree_mujoco_keyboard::resetKeyboardState();
    }

    void update() override
    {
        const auto s = unitree_mujoco_keyboard::snapshotKeyboardState();
        back(s.back);
        start(s.start);
        LB(s.lb);
        RB(s.rb);
        A(s.a);
        B(s.b);
        X(s.x);
        Y(s.y);
        up(s.up);
        down(s.down);
        left(s.left);
        right(s.right);
        LT(s.lt);
        RT(s.rt);
        lx(s.lx);
        ly(s.ly);
        rx(s.rx);
        ry(s.ry);
    }
};


class XBoxJoystick : public unitree::common::UnitreeJoystick
{
public:
    XBoxJoystick(std::string device, int bits = 15)
    : unitree::common::UnitreeJoystick()
    {
        js_ = std::make_unique<Joystick>(device);
        if(!js_->isFound()) {
            std::cout << "Error: Joystick open failed." << std::endl;
            exit(1);
        }
        max_value_ = 1 << (bits - 1);
    }

    void update() override
    {
        js_->getState();
        back(js_->button_[6]);
        start(js_->button_[7]);
        LB(js_->button_[4]);
        RB(js_->button_[5]);
        A(js_->button_[0]);
        B(js_->button_[1]); 
        X(js_->button_[2]);
        Y(js_->button_[3]);
        up(js_->axis_[7] < 0);
        down(js_->axis_[7] > 0);
        left(js_->axis_[6] < 0);
        right(js_->axis_[6] > 0);
        LT(js_->axis_[2] > 0);
        RT(js_->axis_[5] > 0);
        lx(double(js_->axis_[0]) / max_value_);
        ly(-double(js_->axis_[1]) / max_value_);
        rx(double(js_->axis_[3]) / max_value_);
        ry(-double(js_->axis_[4]) / max_value_);
    }
private:
    std::unique_ptr<Joystick> js_;
    int max_value_;
};


class SwitchJoystick : public unitree::common::UnitreeJoystick
{
public:
    SwitchJoystick(std::string device, int bits = 15)
    : unitree::common::UnitreeJoystick()
    {
        js_ = std::make_unique<Joystick>(device);
        if(!js_->isFound()) {
            std::cout << "Error: Joystick open failed." << std::endl;
            exit(1);
        }
        max_value_ = 1 << (bits - 1);
    }

    void update() override
    {
        js_->getState();
        back(js_->button_[10]);
        start(js_->button_[11]);
        LB(js_->button_[6]);
        RB(js_->button_[7]);
        A(js_->button_[0]);
        B(js_->button_[1]); 
        X(js_->button_[3]);
        Y(js_->button_[4]);
        up(js_->axis_[7] < 0);
        down(js_->axis_[7] > 0);
        left(js_->axis_[6] < 0);
        right(js_->axis_[6] > 0);
        LT(js_->axis_[5] > 0);
        RT(js_->axis_[4] > 0);
        lx(double(js_->axis_[0]) / max_value_);
        ly(-double(js_->axis_[1]) / max_value_);
        rx(double(js_->axis_[2]) / max_value_);
        ry(-double(js_->axis_[3]) / max_value_);
    }
private:
    std::unique_ptr<Joystick> js_;
    int max_value_;
};
