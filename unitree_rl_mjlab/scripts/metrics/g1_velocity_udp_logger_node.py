#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
g1_velocity_udp_logger_node_v3.py

ROS 2 Foxy node for standardized Unitree G1 Crouch-Walking experiments.

Functions:
  1. Publishes the commanded velocity on /cmd_vel for traceability.
  2. Sends the same command as UDP packet [vx, vy, yaw_rate] to the patched g1_controller.
  3. Logs IMU data from either:
       - sensor_msgs/msg/Imu
       - unitree_hg/msg/IMUState
  4. Optionally logs motion state from either:
       - nav_msgs/msg/Odometry
       - unitree_go/msg/SportModeState, e.g. /odommodestate on the Unitree G1 setup
  5. Writes a raw CSV and a compact summary CSV.

UDP packet format expected by patched observations.h:
  struct.pack("fff", vx, vy, yaw_rate)

Recommended real robot G1 profile using /odommodestate:
  /usr/bin/python3 g1_velocity_udp_logger_node_v3.py \
    --ros-args \
    -p trial_id:=1 \
    -p vx:=0.30 \
    -p vy:=0.00 \
    -p yaw_rate:=0.50 \
    -p duration:=10.0 \
    -p publish_rate:=50.0 \
    -p udp_ip:=127.0.0.1 \
    -p udp_port:=5005 \
    -p imu_mode:=unitree_hg \
    -p imu_topic:=/secondary_imu \
    -p enable_odom:=true \
    -p odom_mode:=unitree_go \
    -p odom_topic:=/odommodestate \
    -p csv_path:=g1_trial_001.csv

Simulation or ROS-native odometry profile:
  use -p odom_mode:=nav_msgs and set odom_topic to a nav_msgs/msg/Odometry topic.
"""

import csv
import math
import os
import socket
import struct
from typing import Dict, List

import rclpy
from rclpy.node import Node

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu

try:
    from unitree_hg.msg import IMUState
except Exception:
    IMUState = None

try:
    from unitree_go.msg import SportModeState as GoSportModeState
except Exception:
    GoSportModeState = None


def quaternion_to_euler_rad(x: float, y: float, z: float, w: float):
    """Return roll, pitch, yaw in rad from quaternion x,y,z,w."""
    sinr_cosp = 2.0 * (w * x + y * z)
    cosr_cosp = 1.0 - 2.0 * (x * x + y * y)
    roll = math.atan2(sinr_cosp, cosr_cosp)

    sinp = 2.0 * (w * y - z * x)
    if abs(sinp) >= 1.0:
        pitch = math.copysign(math.pi / 2.0, sinp)
    else:
        pitch = math.asin(sinp)

    siny_cosp = 2.0 * (w * z + x * y)
    cosy_cosp = 1.0 - 2.0 * (y * y + z * z)
    yaw = math.atan2(siny_cosp, cosy_cosp)

    return roll, pitch, yaw


def finite_values(values: List[float]) -> List[float]:
    return [v for v in values if math.isfinite(v)]


def rmse(values: List[float]) -> float:
    values = finite_values(values)
    if not values:
        return float("nan")
    return math.sqrt(sum(v * v for v in values) / len(values))


def mean(values: List[float]) -> float:
    values = finite_values(values)
    if not values:
        return float("nan")
    return sum(values) / len(values)


def std(values: List[float]) -> float:
    values = finite_values(values)
    if len(values) < 2:
        return float("nan")
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def min_finite(values: List[float]) -> float:
    values = finite_values(values)
    return min(values) if values else float("nan")


def max_finite(values: List[float]) -> float:
    values = finite_values(values)
    return max(values) if values else float("nan")


class G1VelocityUdpLoggerNode(Node):
    def __init__(self):
        super().__init__("g1_velocity_udp_logger_node")

        # Command parameters
        self.declare_parameter("trial_id", 1)
        self.declare_parameter("vx", 0.30)
        self.declare_parameter("vy", 0.00)
        self.declare_parameter("yaw_rate", 0.50)
        self.declare_parameter("duration", 10.0)
        self.declare_parameter("publish_rate", 50.0)

        # ROS topics
        self.declare_parameter("cmd_topic", "/cmd_vel")
        self.declare_parameter("imu_topic", "/secondary_imu")
        self.declare_parameter("imu_mode", "unitree_hg")  # sensor_msgs or unitree_hg
        self.declare_parameter("enable_odom", False)
        self.declare_parameter("odom_topic", "/odommodestate")
        self.declare_parameter("odom_mode", "unitree_go")  # unitree_go or nav_msgs
        self.declare_parameter("odom_stale_timeout_s", 0.50)
        self.declare_parameter("imu_stale_timeout_s", 0.50)

        # UDP
        self.declare_parameter("udp_ip", "127.0.0.1")
        self.declare_parameter("udp_port", 5005)

        # CSV/output
        self.declare_parameter("csv_path", "g1_velocity_trial.csv")
        self.declare_parameter("write_summary_csv", True)
        self.declare_parameter("summary_csv_path", "")

        # Thresholds and manual annotations
        self.declare_parameter("fall_roll_threshold_rad", 0.80)
        self.declare_parameter("fall_pitch_threshold_rad", 0.80)
        self.declare_parameter("send_zero_after_duration_s", 1.0)
        self.declare_parameter("passive_mode_triggered", False)
        self.declare_parameter("fall_detected_manual", False)
        self.declare_parameter("operator_note", "")

        self.trial_id = int(self.get_parameter("trial_id").value)
        self.vx_cmd = float(self.get_parameter("vx").value)
        self.vy_cmd = float(self.get_parameter("vy").value)
        self.yaw_rate_cmd = float(self.get_parameter("yaw_rate").value)
        self.duration_s = float(self.get_parameter("duration").value)
        self.publish_rate = float(self.get_parameter("publish_rate").value)

        self.cmd_topic = str(self.get_parameter("cmd_topic").value)
        self.imu_topic = str(self.get_parameter("imu_topic").value)
        self.imu_mode = str(self.get_parameter("imu_mode").value).strip().lower()
        self.enable_odom = bool(self.get_parameter("enable_odom").value)
        self.odom_topic = str(self.get_parameter("odom_topic").value)
        self.odom_mode = str(self.get_parameter("odom_mode").value).strip().lower()
        self.odom_stale_timeout_s = float(self.get_parameter("odom_stale_timeout_s").value)
        self.imu_stale_timeout_s = float(self.get_parameter("imu_stale_timeout_s").value)

        self.udp_ip = str(self.get_parameter("udp_ip").value)
        self.udp_port = int(self.get_parameter("udp_port").value)

        self.csv_path = str(self.get_parameter("csv_path").value)
        self.write_summary_csv = bool(self.get_parameter("write_summary_csv").value)
        self.summary_csv_path = str(self.get_parameter("summary_csv_path").value)
        if not self.summary_csv_path:
            base, _ = os.path.splitext(self.csv_path)
            self.summary_csv_path = base + "_summary.csv"

        self.fall_roll_threshold_rad = float(self.get_parameter("fall_roll_threshold_rad").value)
        self.fall_pitch_threshold_rad = float(self.get_parameter("fall_pitch_threshold_rad").value)
        self.zero_after_s = float(self.get_parameter("send_zero_after_duration_s").value)
        self.passive_mode_triggered = bool(self.get_parameter("passive_mode_triggered").value)
        self.fall_detected_manual = bool(self.get_parameter("fall_detected_manual").value)
        self.operator_note = str(self.get_parameter("operator_note").value)

        self.latest_imu_data = {
            "roll": float("nan"), "pitch": float("nan"), "yaw": float("nan"),
            "wx": float("nan"), "wy": float("nan"), "wz": float("nan"),
            "ax": float("nan"), "ay": float("nan"), "az": float("nan"),
            "temperature": float("nan"),
        }
        self.latest_odom_data = {
            "x": float("nan"), "y": float("nan"), "z": float("nan"),
            "yaw": float("nan"), "vx": float("nan"), "vy": float("nan"),
            "yaw_rate": float("nan"), "mode": float("nan"), "error_code": float("nan"),
        }
        self.last_imu_time_s = float("nan")
        self.last_odom_time_s = float("nan")
        self.imu_msg_count = 0
        self.odom_msg_count = 0

        self.start_time = self.get_clock().now()
        self.completed_duration = False
        self.shutdown_started = False

        # UDP socket
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # ROS pub/sub
        self.cmd_pub = self.create_publisher(Twist, self.cmd_topic, 10)

        if self.imu_mode == "sensor_msgs":
            self.imu_sub = self.create_subscription(Imu, self.imu_topic, self.sensor_imu_callback, 50)
        elif self.imu_mode == "unitree_hg":
            if IMUState is None:
                raise RuntimeError(
                    "imu_mode is 'unitree_hg', but unitree_hg.msg.IMUState could not be imported. "
                    "Make sure the Unitree ROS2 environment is sourced."
                )
            self.imu_sub = self.create_subscription(IMUState, self.imu_topic, self.unitree_hg_imu_callback, 50)
        else:
            raise ValueError("imu_mode must be either 'sensor_msgs' or 'unitree_hg'.")

        self.odom_sub = None
        if self.enable_odom:
            if self.odom_mode == "nav_msgs":
                self.odom_sub = self.create_subscription(Odometry, self.odom_topic, self.nav_odom_callback, 50)
            elif self.odom_mode == "unitree_go":
                if GoSportModeState is None:
                    raise RuntimeError(
                        "odom_mode is 'unitree_go', but unitree_go.msg.SportModeState could not be imported. "
                        "Make sure the Unitree ROS2/Unitree interfaces are sourced."
                    )
                self.odom_sub = self.create_subscription(
                    GoSportModeState, self.odom_topic, self.unitree_go_sportmode_callback, 50
                )
            else:
                raise ValueError("odom_mode must be either 'unitree_go' or 'nav_msgs'.")

        # CSV setup
        self.csv_file = open(self.csv_path, mode="w", newline="", encoding="utf-8")
        self.csv_writer = csv.DictWriter(self.csv_file, fieldnames=self.sample_fieldnames())
        self.csv_writer.writeheader()
        self.samples: List[Dict[str, float]] = []

        period = 1.0 / self.publish_rate
        self.timer = self.create_timer(period, self.timer_callback)

        self.get_logger().info("G1 velocity UDP logger node v3 started.")
        self.get_logger().info(
            f"Trial {self.trial_id}: vx={self.vx_cmd:.3f} m/s, "
            f"vy={self.vy_cmd:.3f} m/s, yaw_rate={self.yaw_rate_cmd:.3f} rad/s, "
            f"duration={self.duration_s:.2f} s, rate={self.publish_rate:.1f} Hz"
        )
        self.get_logger().info(
            f"Publishing {self.cmd_topic}, UDP {self.udp_ip}:{self.udp_port}, "
            f"IMU {self.imu_topic} ({self.imu_mode}), "
            f"odom {self.odom_topic if self.enable_odom else 'disabled'} ({self.odom_mode if self.enable_odom else 'none'})"
        )
        self.get_logger().info(f"CSV output: {self.csv_path}")

    def sample_fieldnames(self):
        return [
            "trial_id", "time_s", "phase", "vx_cmd_mps", "vy_cmd_mps", "yaw_rate_cmd_radps", "udp_sent",
            "imu_mode", "imu_topic", "imu_msg_count", "imu_age_s",
            "imu_roll_rad", "imu_pitch_rad", "imu_yaw_rad",
            "imu_ang_vel_x_radps", "imu_ang_vel_y_radps", "imu_ang_vel_z_radps",
            "imu_lin_acc_x_mps2", "imu_lin_acc_y_mps2", "imu_lin_acc_z_mps2", "imu_lin_acc_norm_mps2",
            "imu_temperature",
            "odom_enabled", "odom_mode", "odom_topic", "odom_msg_count", "odom_age_s",
            "odom_x_m", "odom_y_m", "odom_z_m_base_height", "odom_yaw_rad",
            "odom_vx_mps", "odom_vy_mps", "odom_yaw_rate_radps",
            "odom_unitree_mode", "odom_error_code",
            "vx_error_odom_mps", "vy_error_odom_mps", "yaw_rate_error_imu_radps", "yaw_rate_error_odom_radps",
            "fall_threshold_exceeded", "passive_mode_triggered_manual", "fall_detected_manual",
        ]

    def elapsed_s(self) -> float:
        return (self.get_clock().now() - self.start_time).nanoseconds * 1e-9

    def sensor_imu_callback(self, msg: Imu):
        q = msg.orientation
        roll, pitch, yaw = quaternion_to_euler_rad(q.x, q.y, q.z, q.w)
        self.latest_imu_data.update({
            "roll": roll, "pitch": pitch, "yaw": yaw,
            "wx": msg.angular_velocity.x, "wy": msg.angular_velocity.y, "wz": msg.angular_velocity.z,
            "ax": msg.linear_acceleration.x, "ay": msg.linear_acceleration.y, "az": msg.linear_acceleration.z,
            "temperature": float("nan"),
        })
        self.last_imu_time_s = self.elapsed_s()
        self.imu_msg_count += 1

    def unitree_hg_imu_callback(self, msg):
        # unitree_hg/msg/IMUState: quaternion, gyroscope, accelerometer, rpy, temperature.
        # Use rpy directly because Unitree already provides it and quaternion ordering may vary.
        self.latest_imu_data.update({
            "roll": float(msg.rpy[0]), "pitch": float(msg.rpy[1]), "yaw": float(msg.rpy[2]),
            "wx": float(msg.gyroscope[0]), "wy": float(msg.gyroscope[1]), "wz": float(msg.gyroscope[2]),
            "ax": float(msg.accelerometer[0]), "ay": float(msg.accelerometer[1]), "az": float(msg.accelerometer[2]),
            "temperature": float(msg.temperature),
        })
        self.last_imu_time_s = self.elapsed_s()
        self.imu_msg_count += 1

    def nav_odom_callback(self, msg: Odometry):
        p = msg.pose.pose.position
        q = msg.pose.pose.orientation
        _, _, yaw = quaternion_to_euler_rad(q.x, q.y, q.z, q.w)
        self.latest_odom_data.update({
            "x": float(p.x), "y": float(p.y), "z": float(p.z), "yaw": float(yaw),
            "vx": float(msg.twist.twist.linear.x),
            "vy": float(msg.twist.twist.linear.y),
            "yaw_rate": float(msg.twist.twist.angular.z),
            "mode": float("nan"), "error_code": float("nan"),
        })
        self.last_odom_time_s = self.elapsed_s()
        self.odom_msg_count += 1

    def unitree_go_sportmode_callback(self, msg):
        # unitree_go/msg/SportModeState, e.g. /odommodestate.
        # Relevant fields observed on the G1 setup:
        #   position[0:3] -> x, y, z/base height [m]
        #   velocity[0:3] -> vx, vy, vz [m/s]
        #   yaw_speed     -> yaw rate [rad/s]
        #   imu_state.rpy -> roll, pitch, yaw [rad]
        self.latest_odom_data.update({
            "x": float(msg.position[0]),
            "y": float(msg.position[1]),
            "z": float(msg.position[2]),
            "yaw": float(msg.imu_state.rpy[2]),
            "vx": float(msg.velocity[0]),
            "vy": float(msg.velocity[1]),
            "yaw_rate": float(msg.yaw_speed),
            "mode": float(msg.mode),
            "error_code": float(msg.error_code),
        })
        self.last_odom_time_s = self.elapsed_s()
        self.odom_msg_count += 1

    def make_twist(self, vx: float, vy: float, yaw_rate: float) -> Twist:
        msg = Twist()
        msg.linear.x = float(vx)
        msg.linear.y = float(vy)
        msg.linear.z = 0.0
        msg.angular.x = 0.0
        msg.angular.y = 0.0
        msg.angular.z = float(yaw_rate)
        return msg

    def send_udp_command(self, vx: float, vy: float, yaw_rate: float) -> bool:
        try:
            packet = struct.pack("fff", float(vx), float(vy), float(yaw_rate))
            self.udp_socket.sendto(packet, (self.udp_ip, self.udp_port))
            return True
        except OSError as exc:
            self.get_logger().error(f"UDP send failed: {exc}")
            return False

    def timer_callback(self):
        t = self.elapsed_s()
        if t <= self.duration_s:
            phase = "active"
            vx = self.vx_cmd
            vy = self.vy_cmd
            yaw_rate = self.yaw_rate_cmd
        elif t <= self.duration_s + self.zero_after_s:
            phase = "zero_after"
            vx = 0.0
            vy = 0.0
            yaw_rate = 0.0
            self.completed_duration = True
        else:
            if not self.shutdown_started:
                self.shutdown_started = True
                self.finish_and_shutdown()
            return

        self.cmd_pub.publish(self.make_twist(vx, vy, yaw_rate))
        udp_sent = self.send_udp_command(vx, vy, yaw_rate)
        row = self.build_sample_row(t, phase, vx, vy, yaw_rate, udp_sent)
        self.csv_writer.writerow(row)
        self.csv_file.flush()
        if phase == "active":
            self.samples.append(row)

    def build_sample_row(self, t: float, phase: str, vx: float, vy: float, yaw_rate: float, udp_sent: bool):
        imu = self.latest_imu_data
        odom = self.latest_odom_data

        imu_age = t - self.last_imu_time_s if math.isfinite(self.last_imu_time_s) else float("nan")
        odom_age = t - self.last_odom_time_s if math.isfinite(self.last_odom_time_s) else float("nan")

        imu_roll = imu["roll"]
        imu_pitch = imu["pitch"]
        imu_wz = imu["wz"]
        imu_ax = imu["ax"]
        imu_ay = imu["ay"]
        imu_az = imu["az"]
        if all(math.isfinite(v) for v in [imu_ax, imu_ay, imu_az]):
            imu_acc_norm = math.sqrt(imu_ax * imu_ax + imu_ay * imu_ay + imu_az * imu_az)
        else:
            imu_acc_norm = float("nan")

        odom_x = odom["x"]
        odom_y = odom["y"]
        odom_z = odom["z"]
        odom_yaw = odom["yaw"]
        odom_vx = odom["vx"]
        odom_vy = odom["vy"]
        odom_yaw_rate = odom["yaw_rate"]

        vx_error_odom = vx - odom_vx if math.isfinite(odom_vx) else float("nan")
        vy_error_odom = vy - odom_vy if math.isfinite(odom_vy) else float("nan")
        yaw_error_imu = yaw_rate - imu_wz if math.isfinite(imu_wz) else float("nan")
        yaw_error_odom = yaw_rate - odom_yaw_rate if math.isfinite(odom_yaw_rate) else float("nan")

        fall_threshold_exceeded = False
        if math.isfinite(imu_roll) and abs(imu_roll) > self.fall_roll_threshold_rad:
            fall_threshold_exceeded = True
        if math.isfinite(imu_pitch) and abs(imu_pitch) > self.fall_pitch_threshold_rad:
            fall_threshold_exceeded = True

        return {
            "trial_id": self.trial_id,
            "time_s": round(t, 5),
            "phase": phase,
            "vx_cmd_mps": round(vx, 6),
            "vy_cmd_mps": round(vy, 6),
            "yaw_rate_cmd_radps": round(yaw_rate, 6),
            "udp_sent": int(udp_sent),

            "imu_mode": self.imu_mode,
            "imu_topic": self.imu_topic,
            "imu_msg_count": self.imu_msg_count,
            "imu_age_s": imu_age,
            "imu_roll_rad": imu["roll"],
            "imu_pitch_rad": imu["pitch"],
            "imu_yaw_rad": imu["yaw"],
            "imu_ang_vel_x_radps": imu["wx"],
            "imu_ang_vel_y_radps": imu["wy"],
            "imu_ang_vel_z_radps": imu["wz"],
            "imu_lin_acc_x_mps2": imu["ax"],
            "imu_lin_acc_y_mps2": imu["ay"],
            "imu_lin_acc_z_mps2": imu["az"],
            "imu_lin_acc_norm_mps2": imu_acc_norm,
            "imu_temperature": imu["temperature"],

            "odom_enabled": int(self.enable_odom),
            "odom_mode": self.odom_mode if self.enable_odom else "disabled",
            "odom_topic": self.odom_topic if self.enable_odom else "disabled",
            "odom_msg_count": self.odom_msg_count,
            "odom_age_s": odom_age,
            "odom_x_m": odom_x,
            "odom_y_m": odom_y,
            "odom_z_m_base_height": odom_z,
            "odom_yaw_rad": odom_yaw,
            "odom_vx_mps": odom_vx,
            "odom_vy_mps": odom_vy,
            "odom_yaw_rate_radps": odom_yaw_rate,
            "odom_unitree_mode": odom["mode"],
            "odom_error_code": odom["error_code"],

            "vx_error_odom_mps": vx_error_odom,
            "vy_error_odom_mps": vy_error_odom,
            "yaw_rate_error_imu_radps": yaw_error_imu,
            "yaw_rate_error_odom_radps": yaw_error_odom,

            "fall_threshold_exceeded": int(fall_threshold_exceeded),
            "passive_mode_triggered_manual": int(self.passive_mode_triggered),
            "fall_detected_manual": int(self.fall_detected_manual),
        }

    def compute_summary(self) -> Dict[str, float]:
        s = self.samples

        def col(name: str) -> List[float]:
            out = []
            for row in s:
                value = row.get(name, float("nan"))
                try:
                    out.append(float(value))
                except Exception:
                    pass
            return out

        imu_roll = col("imu_roll_rad")
        imu_pitch = col("imu_pitch_rad")
        imu_yaw_rate = col("imu_ang_vel_z_radps")
        imu_acc_norm = col("imu_lin_acc_norm_mps2")
        imu_age = col("imu_age_s")

        odom_z = col("odom_z_m_base_height")
        odom_vx = col("odom_vx_mps")
        odom_vy = col("odom_vy_mps")
        odom_yaw_rate = col("odom_yaw_rate_radps")
        odom_age = col("odom_age_s")

        vx_err = col("vx_error_odom_mps")
        vy_err = col("vy_error_odom_mps")
        yaw_err_imu = col("yaw_rate_error_imu_radps")
        yaw_err_odom = col("yaw_rate_error_odom_radps")
        fall_threshold_flags = col("fall_threshold_exceeded")

        runtime_actual_s = min(self.elapsed_s(), self.duration_s)
        completed = self.completed_duration or runtime_actual_s >= self.duration_s
        fall_threshold_exceeded = int(any(v > 0.5 for v in fall_threshold_flags))
        fall_detected = int(bool(self.fall_detected_manual) or bool(fall_threshold_exceeded))
        successful_trial = int(completed and not self.passive_mode_triggered and not bool(fall_detected))

        return {
            "trial_id": self.trial_id,
            "vx_cmd_mps": self.vx_cmd,
            "vy_cmd_mps": self.vy_cmd,
            "yaw_rate_cmd_radps": self.yaw_rate_cmd,
            "duration_cmd_s": self.duration_s,
            "runtime_actual_s": runtime_actual_s,
            "publish_rate_hz": self.publish_rate,
            "sample_count_active": len(s),
            "successful_trial": successful_trial,
            "passive_mode_triggered_manual": int(self.passive_mode_triggered),
            "fall_detected": fall_detected,
            "fall_threshold_exceeded": fall_threshold_exceeded,

            "imu_mode": self.imu_mode,
            "imu_topic": self.imu_topic,
            "imu_msg_count": self.imu_msg_count,
            "imu_age_mean_s": mean(imu_age),
            "imu_yaw_rate_mean_radps": mean(imu_yaw_rate),
            "imu_yaw_rate_std_radps": std(imu_yaw_rate),
            "imu_yaw_rate_rmse_radps": rmse(yaw_err_imu),
            "imu_roll_abs_max_rad": max_finite([abs(v) for v in imu_roll]),
            "imu_pitch_abs_max_rad": max_finite([abs(v) for v in imu_pitch]),
            "imu_acc_norm_mean_mps2": mean(imu_acc_norm),
            "imu_acc_norm_std_mps2": std(imu_acc_norm),

            "enable_odom": int(self.enable_odom),
            "odom_mode": self.odom_mode if self.enable_odom else "disabled",
            "odom_topic": self.odom_topic if self.enable_odom else "disabled",
            "odom_msg_count": self.odom_msg_count,
            "odom_age_mean_s": mean(odom_age),
            "odom_vx_mean_mps": mean(odom_vx),
            "odom_vy_mean_mps": mean(odom_vy),
            "odom_yaw_rate_mean_radps": mean(odom_yaw_rate),
            "odom_vx_rmse_mps": rmse(vx_err),
            "odom_vy_rmse_mps": rmse(vy_err),
            "odom_yaw_rate_rmse_radps": rmse(yaw_err_odom),
            "base_height_mean_m": mean(odom_z),
            "base_height_std_m": std(odom_z),
            "base_height_min_m": min_finite(odom_z),
            "base_height_max_m": max_finite(odom_z),

            "csv_path": self.csv_path,
            "operator_note": self.operator_note,
        }

    def finish_and_shutdown(self):
        self.cmd_pub.publish(self.make_twist(0.0, 0.0, 0.0))
        self.send_udp_command(0.0, 0.0, 0.0)
        summary = self.compute_summary()

        if self.write_summary_csv:
            with open(self.summary_csv_path, mode="w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(summary.keys()))
                writer.writeheader()
                writer.writerow(summary)

        self.csv_file.close()
        self.get_logger().info("Experiment finished.")
        self.get_logger().info(f"Raw CSV: {self.csv_path}")
        if self.write_summary_csv:
            self.get_logger().info(f"Summary CSV: {self.summary_csv_path}")
        self.get_logger().info(
            "Summary: "
            f"success={summary['successful_trial']}, "
            f"runtime={summary['runtime_actual_s']:.2f}s, "
            f"imu_msgs={summary['imu_msg_count']}, "
            f"odom_msgs={summary['odom_msg_count']}, "
            f"imu_yaw_rmse={summary['imu_yaw_rate_rmse_radps']:.4f} rad/s, "
            f"odom_vx_rmse={summary['odom_vx_rmse_mps']:.4f} m/s, "
            f"base_height_mean={summary['base_height_mean_m']:.4f} m"
        )
        rclpy.shutdown()


def main(args=None):
    rclpy.init(args=args)
    node = G1VelocityUdpLoggerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().warn("KeyboardInterrupt received. Sending zero command and writing summary.")
        node.completed_duration = False
        node.finish_and_shutdown()


if __name__ == "__main__":
    main()
