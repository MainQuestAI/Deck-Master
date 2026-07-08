# Acceptance Matrix

| ID | Requirement | Milestone | Blocking | Evidence |
|---|---|---|---:|---|
| OSM-001 | M1 public Technical Preview 状态可见 | M1 | P0 | README + CHANGELOG + release checklist |
| OSM-002 | Apache-2.0 license 可被识别 | M1 | P0 | LICENSE + pyproject metadata |
| OSM-003 | DCO / CONTRIBUTING / SECURITY / CODE_OF_CONDUCT 齐备 | M1 | P0 | governance files |
| OSM-004 | `pyproject.toml[dev]` 驱动本地和 CI 安装 | M1 | P0 | clean install evidence |
| OSM-005 | console script `deck-master` 可用 | M1 | P1 | `deck-master --help` |
| OSM-006 | 未配置 backend 不返回 `bound_verified` | M1 | P0 | negative tests |
| OSM-007 | production 命令在 backend 未配置时阻断 | M1 | P0 | CLI negative test |
| OSM-008 | `preview-gate` 可验证 fixture demo | M1 | P0 | preview-gate output |
| OSM-009 | README / Quick Start 10 分钟 demo 路径可复现 | M1 | P0 | demo run evidence |
| OSM-010 | 公开 fixture demo 生成 10+ 页 | M1 | P0 | demo run manifest |
| OSM-011 | demo 无 placeholder / 本机路径 / 敏感信息 | M1 | P0 | rg scan |
| OSM-012 | Git 不再跟踪 `.gstack/qa-reports` | M1 | P0 | `git ls-files .gstack` |
| OSM-013 | release tree 含 README / LICENSE / Known Limitations | M1 | P0 | release tree inspection |
| OSM-014 | Review Desk 无 `.glass-panel` / `backdrop-filter` | M1 | P0 | static scan |
| OSM-015 | Review Desk 命名统一 | M1 | P0 | static scan + screenshot |
| OSM-016 | 主动作琥珀铜、字体方案明确 | M1 | P0 | CSS scan + screenshot |
| OSM-017 | unittest 全量通过 | M1 | P0 | command output |
| OSM-018 | pytest 合约子集通过 | M1 | P0 | command output |
| OSM-019 | Review Desk 异常路径分歧已修复或记录 | M1 | P1 | release checklist |
| OSM-020 | production 外部独立仓依赖完成 M2 处置 | M2 | P0 | release checklist |
| OSM-021 | 本地 POST 写操作有 token 或 origin 校验 | M2 | P0 | tests + SECURITY |
| OSM-022 | `rc-gate --skip-browser-smoke` 通过 | M2 | P0 | rc gate evidence |
| OSM-023 | `rc-gate --require-browser-smoke` 通过 | M2 | P0 | browser smoke evidence |
| OSM-024 | GitHub 社区入口齐备 | M2 | P1 | templates + ROADMAP |
