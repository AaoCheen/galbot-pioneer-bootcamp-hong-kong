"""查询右臂关节角和末端位姿：在 HPU 的 SDK 环境运行，不发送运动指令。"""

import math
import time

from galbot_sdk.g1 import GalbotMotion, GalbotRobot, MotionStatus


# 查询的目标坐标系：右臂末端安装坐标系。
# 它不一定是夹爪指尖或夹持中心，取决于机器人的工具定义。
END_EFFECTOR_FRAME = "right_arm_end_effector_mount_link"

# 参考坐标系：下面的位置和朝向都相对于 base_link 表达。
REFERENCE_FRAME = "base_link"

# 关节查询与末端查询都针对右臂，方便对照两种表示。
JOINT_GROUP = "right_arm"

# motion 查询末端位姿；robot 查询关节状态并管理 SDK 退出流程。
motion = GalbotMotion()
robot = GalbotRobot()

try:
    if not motion.init():
        raise RuntimeError("GalbotMotion 初始化失败")
    if not robot.init():
        raise RuntimeError("GalbotRobot 初始化失败")

    # 刚初始化时等待数据到达；等待并不保证所有服务已经就绪。
    time.sleep(1)

    print("========== 1. 右臂关节表示 ==========")
    # 返回带有关节名称的状态对象，避免凭列表下标猜测对应关系。
    # 本次只使用其中的 position 属性，即每个关节相对零位的角度。
    try:
        joint_states = robot.get_joint_states([JOINT_GROUP], [])
        if not joint_states:
            print("未获取到右臂关节状态，请检查状态反馈服务。")
        else:
            joint_names = [state.joint_name for state in joint_states]
            joint_positions = [state.position for state in joint_states]
            for state in joint_states:
                print(
                    f"{state.joint_name}: {state.position:.4f} rad "
                    f"（约 {math.degrees(state.position):.2f}°）"
                )
            print(f"\n关节数量：{len(joint_states)}")
            print(f"关节顺序：{joint_names}")
            print(f"关节角列表（单位：rad）：\n{joint_positions}")
    except Exception as exc:
        # 关节查询失败时仍尝试下面的末端查询，保留报错便于排查。
        print(f"关节查询异常：{exc!r}")

    print("\n========== 2. 右臂末端位姿表示 ==========")
    print(f"末端坐标系：{END_EFFECTOR_FRAME}")
    print(f"参考坐标系：{REFERENCE_FRAME}")

    # 返回两个值：查询状态 status，以及位姿列表 pose。
    status, pose = motion.get_end_effector_pose(
        end_effector_frame=END_EFFECTOR_FRAME,
        reference_frame=REFERENCE_FRAME,
    )
    print(f"查询状态：{status}")

    if status == MotionStatus.SUCCESS:
        # 前 3 个数为位置，单位为米；后 4 个数为姿态四元数，无量纲。
        # Python 切片不包含右端下标：0:3 取下标 0、1、2。
        position = pose[0:3]
        quaternion = pose[3:7]

        print(f"\n完整位姿 [x, y, z, qx, qy, qz, qw]：\n{pose}")
        print("\n末端位置：")
        print(f"  x = {position[0]:.4f} m")
        print(f"  y = {position[1]:.4f} m")
        print(f"  z = {position[2]:.4f} m")
        print("\n末端姿态（四元数，不是四个角度）：")
        print(f"  qx = {quaternion[0]:.6f}")
        print(f"  qy = {quaternion[1]:.6f}")
        print(f"  qz = {quaternion[2]:.6f}")
        print(f"  qw = {quaternion[3]:.6f}")
        print("\n这 7 个数描述末端位置与朝向，不是 7 个关节角，也不含夹爪开合。")
    else:
        print("查询未成功，请检查坐标系名称、TF 数据及相关服务是否就绪。")

    print("\n========== 3. 两种表示的区别 ==========")
    print("关节表示：描述右臂各关节分别转了多少，单位为 rad。")
    print("末端表示：描述末端相对 base_link 的位置（米）和朝向（四元数）。")
    print("两种表示都不包含夹爪开合宽度，夹爪需要另外查询。")
    print("本脚本依次查询两种数据，不保证来自完全相同的采样时刻。")

finally:
    # 无论成功还是异常，都按官方示例释放 SDK 资源。
    robot.request_shutdown()
    robot.wait_for_shutdown()
    robot.destroy()
    print("\nSDK 资源已释放。")
