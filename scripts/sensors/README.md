# 只读传感器探索

在已配置 `galbot_sdk.g1` 的机器人 HPU Python 环境中运行，保留 `common.py` 在同一目录。

```bash
python 01_sensor_inventory.py --sensor imu
python 02_imu_observe.py --samples 30 --interval 0.2
python 03_lidar_observe.py
python 04_ultrasonic_observe.py
python 05_sensor_health_check.py
```

这些脚本只读状态和传感器，不发送运动目标。每次运行保存 JSONL 摘要和 Markdown 报告，雷达额外保存最后成功帧 PLY。单次检查只能确认收到数据；连续检查才比较时间戳。OBSERVED 是基础观测状态，不替代精度标定。

无需机器人也能运行：

```bash
python3 -m unittest discover -s scripts/sensors -p test_offline.py -v
```

[详细学习笔记](../../docs/labs/sensors/README.md) · [项目首页](../../README.md)
