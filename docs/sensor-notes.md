# CPU 使用率与主板 Vcore 说明

本文说明 WebOBS 的读数口径和特定主板电压换算，供核对传感器来源时使用。

## CPU 总体使用率

默认读取 Windows PDH `Processor Information(_Total) / % Processor Utility`。
LibreHardwareMonitor 的 CPU Total 主要反映忙碌时间，与 Processor Utility
的计算口径不同，因此两者瞬时数值可能不同。Windows 整体使用率不可用时，
程序才回退到硬件库或 Windows 忙碌时间；用户手动绑定的传感器保持优先。

## Vcore 主板换算

LibreHardwareMonitor 0.9.6 未识别本机完整型号
`ASUS ROG STRIX Z790-A GAMING WIFI S`，其 Nuvoton NCT6798D
Vcore 通道使用通用的未缩放映射。WebOBS 为此型号补充：

```text
Vcore = 原始通道值 × (1 + 15 / 136)
```

匹配条件包含完整主板名称、父设备、芯片、通道
`/lpc/nct6798d/0/voltage/0`、Vcore 名称及原有分压参数。
其他主板与通道保持后端原有配置，已有分压换算时不会再次应用。
API 同时保留原始值与换算参数。这个转换只处理读数，不修改硬件寄存器或 BIOS。

| 原始通道值 | 换算值，保留三位小数 |
| --- | --- |
| 1.128 V | 1.252 V |
| 1.136 V | 1.261 V |
| 1.144 V | 1.270 V |
| 1.152 V | 1.279 V |
| 0.640 V | 0.711 V |

该系数通过本机游戏加加的读数阶梯与原始 ADC 通道对照得到，
上游 ASUS TUF GAMING B760M-PLUS WIFI D4 配置也使用同一分压参数。
它不是华硕提供的此 Z790-A 型号原理图参数，且没有使用电压表验证绝对精度。
不同软件的独立采样时刻不保证同步；此型号以外的主板没有因此获得新增校准保证。

## 缺失与无效读数

- CPU 电压自动选择主板 Vcore，不用 CPU VID 代替。
- CPU 功耗选择 CPU Package，不用 CPU Cores 功耗代替。
- 缺少底层温度 / 时钟读数时，无效的 CPU 功耗 0 W 会被排除。
- 手动绑定失效时显示“—”，不会自动读取另一设备或另一传感器。
- 默认硬件库采样周期为 1000 ms；页面数字直接显示最新样本，指针保留动画。

## 项目内验证

`tests/test_board_profiles.py` 覆盖主板匹配、低电压、缺失读数、
原始快照不被修改以及重复换算保护。
`tests/test_monitor.py` 覆盖 Windows 使用率来源优先级、PDH 无效数据、
手动绑定与功率模型。

本机历史采样与打包验证记录保留在本地 `verification/`，不随 Git 仓库分发。
本文保留读数解释与验证边界，便携包同时提供 `SENSOR-NOTES.md` 副本。

## 原始资料

- [微软：Processor Time 与 Processor Utility 的区别](https://jpwinsup.github.io/blog/2022/07/15/Performance/SystemResource/PerformanceCounterProcessor/)
- [LibreHardwareMonitor 0.9.6 主板配置与分压公式](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/blob/v0.9.6/LibreHardwareMonitorLib/Hardware/Motherboard/SuperIOHardware.cs)
- [上游 ASUS B760M 主板支持补丁](https://github.com/LibreHardwareMonitor/LibreHardwareMonitor/pull/2097)
