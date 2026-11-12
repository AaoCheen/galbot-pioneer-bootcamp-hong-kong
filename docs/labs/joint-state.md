# 关节状态读取：结果与解释

记录日期：2026-11-12。来源为用户提供的终端输出，未由助手重新执行；没有检查远端脚本源码。

运行位置：HPU 主机 `robot-hpu` 的 `~/galbot-learning`。

```bash
python 01_joint_state_reading.py
```

## 重点解释

### 1. 三种选取关节的方式

- 按组读取：例如 `right_arm`，读取右臂的 7 个关节。
- 按名称读取：例如 `right_arm_joint1`、`right_arm_joint3`，只读取指定关节。
- 默认范围读取：本次返回 25 个位置值。这是本次接口默认返回范围，不等于“机器人总共只有 25 个电机”，也不意味着包含所有夹爪或末端设备。

本地 SDK 示例中的对应接口形式：

```python
robot.get_joint_positions(["right_arm"], [])
robot.get_joint_positions([], ["right_arm_joint1", "right_arm_joint3"])
robot.get_joint_positions([], [])
robot.get_joint_states(["left_arm"], [])
```

`get_joint_positions` 返回位置数值列表；`get_joint_states` 返回包含关节名及多个状态字段的对象列表。明确指定关节名时，本地 SDK 文档说明关节名优先于关节组。

默认列表应配合对应的关节名解读，不能只凭数组下标猜关节。本地 SDK 头文件说明 G1 默认组顺序为 `chassis → head → left_arm → right_arm → leg`；实际运行版本仍应通过关节名核对。

### 2. 左臂完整状态各字段

| 字段 | 含义 | 本次打印单位 |
|---|---|---|
| `position` | 关节相对定义零位的角度，不是末端空间坐标 | rad，radian，弧度 |
| `velocity` | 角度随时间的变化率，即关节转速 | rad/s，弧度每秒 |
| `acceleration` | 角速度随时间的变化率 | rad/s²，弧度每二次方秒 |
| `effort` | 关节力矩字段 | N·m，newton-metre，牛顿米 |
| `current` | 电机电流字段 | A，ampere，安培 |

**角度换算**：`角度（°）= 弧度 × 180 / π`；`π rad = 180°`。右臂关节 1 的 `-1.6262 rad` 约为 `-93.18°`。正负号表示相对关节定义正方向的角度，不能直接理解成统一的“向左／向右”。

**第 7 个右臂值仍是手臂关节角**：`right_arm_joint7 = 0.0007 rad`，不是夹爪开合宽度。

### 3. 如何理解本次读数？

- 按组和按关节名读到的右臂关节 1、3 一致，说明这次两种选取方式的输出相互对应。
- 左臂速度和加速度均打印为 `0.0000`，表示接口在该次读取中报告零到此精度；是否为真实静止、微小值被舍入或字段未有效提供，需要结合连续读数与服务定义判断。
- **速度为零，电流仍可非零**：电机保持姿态、抵抗重力时也可能需要电流。比如左臂关节 4 报告 `-3.1490 A`，不等于它一定在运动。
- **负电流不等于故障，也不能直接解释成充电**：它通常与驱动器定义的方向／符号有关，具体含义取决于底层约定。
- **`effort = 0` 不能直接推断真实力矩为零**：尚未核实该字段是否提供有效反馈。电流也不能不经电机参数、减速比等换算就当成关节力矩。
- 单次读数用于了解当前报告状态，不能单独证明传感器或全部状态字段正常。

## 原始输出

```text
galbot@robot-hpu:~/galbot-learning$ python 01_joint_state_reading.py

========== 1. 按关节组读取右臂位置 ==========
right_arm_joint1: -1.6262 rad
right_arm_joint2: 1.3027 rad
right_arm_joint3: 0.6611 rad
right_arm_joint4: 1.8031 rad
right_arm_joint5: -0.0516 rad
right_arm_joint6: 0.5525 rad
right_arm_joint7: 0.0007 rad

========== 2. 按具体关节名读取 ==========
right_arm_joint1: -1.6262 rad
right_arm_joint3: 0.6611 rad

========== 3. 使用默认关节范围读取 ==========
默认范围内的关节数量: 25
全部关节位置（单位：rad）: [0.0038487577438354494, 0.02852556037902832, 0.03068075370788574, 0.017623708724975585, 0.4999099671840668, -0.2143461, 1.905155897140503, -1.4942879676818848, -0.7320905327796936, -1.6926499605178833, -0.005513494834303856, -0.7128447890281677, 0.29155200719833374, -1.626187801361084, 1.3026596307754517, 0.6611429452896118, 1.8031222820281982, -0.051626838743686676, 0.5525432825088501, 0.0007190756732597947, 0.4992268681526184, 1.4986274242401123, 0.9992566704750061, -0.000431432097684592, -0.00011984225420746952]

========== 4. 读取左臂完整状态 ==========
left_arm_joint1: position=1.9052 rad, velocity=0.0000 rad/s, acceleration=0.0000 rad/s^2, effort=0.0000 N*m, current=1.5900 A
left_arm_joint2: position=-1.4943 rad, velocity=0.0000 rad/s, acceleration=0.0000 rad/s^2, effort=0.0000 N*m, current=-0.2000 A
left_arm_joint3: position=-0.7321 rad, velocity=0.0000 rad/s, acceleration=0.0000 rad/s^2, effort=0.0000 N*m, current=-0.9910 A
left_arm_joint4: position=-1.6926 rad, velocity=0.0000 rad/s, acceleration=0.0000 rad/s^2, effort=0.0000 N*m, current=-3.1490 A
left_arm_joint5: position=-0.0055 rad, velocity=0.0000 rad/s, acceleration=0.0000 rad/s^2, effort=0.0000 N*m, current=-0.3690 A
left_arm_joint6: position=-0.7128 rad, velocity=0.0000 rad/s, acceleration=0.0000 rad/s^2, effort=0.0000 N*m, current=-0.3810 A
left_arm_joint7: position=0.2916 rad, velocity=0.0000 rad/s, acceleration=0.0000 rad/s^2, effort=0.0000 N*m, current=-0.2560 A
```

接口说明依据：本地 `GalbotSDK/examples/g1/python/galbot_robot/get_joint_positions.py`、`get_joint_states.py`，以及 `galbot_robot.hpp`、`galbot_sdk_type.hpp`。远端已安装 SDK 的版本和各反馈字段有效性尚未在此核实。


[返回项目首页](../../README.md)
