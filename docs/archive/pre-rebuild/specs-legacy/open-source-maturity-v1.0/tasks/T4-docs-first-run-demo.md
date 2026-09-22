# T4 — Docs First Run Demo

## 1. 目标

重写 README 和 Quick Start，让外部用户 10 分钟跑通 fixture demo。

## 2. In Scope

1. `README.md`
2. `docs/quick-start.md`
3. `docs/known-limitations.md`
4. `scripts/demo.sh`
5. `skills/deck-master/SKILL.md`
6. `skills/ppt-master/SKILL.md`

## 3. 必须实现

1. README 首屏说明 What / Status / Install / Run Demo / Review Desk / Boundaries / License。
2. Quick Start 给出完整命令。
3. production 文档不把 fixture-only 路径写成正式生产路径。
4. Known Limitations 说明未配置 backend 的边界。

## 4. 验证

```bash
bash scripts/demo.sh
rg -n "fixture-safe|dev-allow-unsetup|production|Technical Preview|Known Limitations" README.md docs/quick-start.md docs/known-limitations.md skills/deck-master/SKILL.md skills/ppt-master/SKILL.md
```

## 5. 成功标准

外部用户能按文档跑通 demo，并理解 production backend 仍需 M2 证明。
