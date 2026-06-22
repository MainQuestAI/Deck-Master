# v0.9.16 RC Checklist

## Code & Contract

- [ ] A0–A5 完成
- [ ] B1–B5 完成
- [ ] C1–C5 完成
- [ ] 所有 canonical schema 已提交
- [ ] spec deviation 已关闭或明确接受
- [ ] 全量测试通过
- [ ] git diff check clean

## Production Truth

- [ ] Production placeholder = 0
- [ ] Fake extension failure matrix 全部阻断
- [ ] Required artifact parse = 100%
- [ ] Source fingerprint stale test 通过
- [ ] run/session binding = 100%
- [ ] final page count = 100%

## Delivery

- [ ] HTML 可打开
- [ ] PDF 可打开
- [ ] 每页 PNG 可打开
- [ ] PPTX 可打开
- [ ] PPTX editability 已声明
- [ ] Artifact manifest 完整
- [ ] Lineage 完整
- [ ] Final readiness ready
- [ ] Export package hash 已记录

## Release

- [ ] Release tree 自包含
- [ ] 原仓移动后 CLI 可用
- [ ] Clean install
- [ ] Upgrade from 0.9.13
- [ ] Rollback
- [ ] Codex targets ready
- [ ] Claude Code targets ready
- [ ] Release archive
- [ ] SHA256SUMS
- [ ] Capability lock

## Real Benchmark

- [ ] ≥3 real cases
- [ ] median first-pass acceptance ≥65%
- [ ] each case acceptance ≥50%
- [ ] review-ready ratio ≤60%
- [ ] client-visible P0 = 0
- [ ] artifact validity = 100%
- [ ] private source scan clean
- [ ] human review evidence complete

## Documentation

- [ ] Quick Start 与 CLI 一致
- [ ] Agent playbook 与实际路径一致
- [ ] Migration guide
- [ ] Troubleshooting
- [ ] Known limitations
- [ ] Release notes
- [ ] 不宣称 flat-image fully editable

只有全部勾选后，才能写：`v0.9.16 is an RC candidate`。
