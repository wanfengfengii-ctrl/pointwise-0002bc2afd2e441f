# 换接事故修复说明

## 根因

1. **接纳改拍**（`capture/recording.py`）：旧 `ingest` 把换接拍（同拍 `close`/`open`）上的采样改记为下一拍再固定，证据里 `r`、`s` 的原拍 1 被写成 2，违反"固定证据保留原拍"。
2. **核定单路贪心且不看封账**（`qualify/replay.py`）：旧 `iter_matching_interpretations` 只按控制原序做一次贪心扫描，既不枚举同拍跨通道的各种先后，也不校验完整顺序的锁存次数是否等于设备封账。于是换接拍上的 `r` 被漏出 A 的窗口、又被当作 B 的首样确认，封账 2 次也未参与核定。

## 修复

- `capture/recording.py`：接纳只做校验与封账核对，通道按录制原样固定（原拍、各通道原序、事件身份、原读值、封账次数），不再改拍。
- `qualify/replay.py`：按拍分组重放。早拍先行；同拍内枚举两通道保序的全部交错；逐条完整顺序模拟"开启期间第一条读数锁存"。只保留锁存次数等于封账的完整顺序，汇总各曝光候选（按采样位置排序）与空样见证；无符合封账的顺序时不产生任何解释，`qualify_release` 抛 `UnexplainableRecording` 拒发，证据保留、不产生成果或回执。`qualify/exposure.py` 中只被旧贪心使用的 `first_in_window` 随之移除，接口与数据类型不变。

## 实测

- `python3 -B -m unittest discover -s tests -t . -v`：22 项全部通过（原 19 项保留，新增 `tests/test_interleaving.py` 3 项：同拍开启边界双候选、同拍关闭边界由封账选定锁存/空样、同窗同拍只锁通道首条）。
- 换接样例：A 确认 `r=17`（位置 0、拍 1），B 待复检 `s=23`（位置 1、拍 1）、`t=31`（位置 2、拍 2），两曝光均不可空；稳定样例 C 确认 `early-c`。
- 单读数 `r` 换接：封账 1 时 A、B 各持候选 `r` 且均可空、均待复检；封账 2 时拒发，证据保留，成果与回执均为空。
- `python3 -B -m station demo` 与 README 的 register/ingest/qualify/pickup 命令序列实测通过，重开归档后按成果号取件，待复检条目出处与固定证据一致。
