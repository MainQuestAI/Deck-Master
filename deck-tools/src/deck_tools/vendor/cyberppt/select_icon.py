#!/usr/bin/env python3
"""Index, search, and sync CyberPPT SVG icons without loading the whole library."""

from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


SVG_NS_RE = re.compile(r"\{.*\}")
WORD_RE = re.compile(r"[a-z0-9]+")
COMMENT_RE = re.compile(r"<!--(.*?)-->", re.DOTALL)
TAGS_LINE_RE = re.compile(r"^\s*tags\s*:\s*\[([^\]]*)\]", re.MULTILINE)
CATEGORY_LINE_RE = re.compile(r"^\s*category\s*:\s*([^\n]+)", re.MULTILINE)

# High-frequency Chinese commercial/consulting terms mapped to Tabler English terms.
# Earlier terms in each tuple carry slightly higher relevance when scoring results.
ZH_SYNONYMS: dict[str, tuple[str, ...]] = {
    "供应链": ("truck", "package", "delivery", "cargo", "route", "box", "forklift"),
    "物流": ("truck", "delivery", "cargo", "package", "ship", "plane", "route"),
    "运输": ("truck", "transport", "delivery", "cargo", "ship", "train"),
    "配送": ("truck", "delivery", "package", "box", "route"),
    "仓储": ("building", "warehouse", "package", "box", "forklift", "stack"),
    "库存": ("package", "box", "boxes", "stack", "warehouse", "clipboard"),
    "安全": ("shield", "lock", "safety", "protect", "security", "key"),
    "合规": ("shield", "check", "scale", "gavel", "certificate", "file"),
    "风控": ("shield", "alert", "radar", "lock", "eye", "security"),
    "防护": ("shield", "protect", "lock", "safety", "umbrella"),
    "权限": ("lock", "key", "shield", "user"),
    "加密": ("lock", "key", "fingerprint", "shield"),
    "增长": ("trending", "chart", "growth", "arrow", "graph", "rocket"),
    "收益": ("coin", "currency", "trending", "chart", "cash", "wallet"),
    "营收": ("currency", "coin", "chart", "trending", "cash", "report"),
    "利润": ("coin", "currency", "cash", "trending", "pig", "wallet"),
    "成本": ("coin", "currency", "calculator", "wallet", "receipt", "money"),
    "预算": ("calculator", "wallet", "coin", "currency", "report", "chart"),
    "财务": ("calculator", "coin", "currency", "receipt", "report", "bank"),
    "资金": ("coin", "cash", "wallet", "currency", "bank", "money"),
    "投资": ("trending", "coin", "chart", "briefcase", "currency", "diamond"),
    "价格": ("tag", "coin", "currency", "receipt", "discount"),
    "指标": ("chart", "gauge", "dashboard", "analytics", "target", "trending"),
    "趋势": ("trending", "chart", "graph", "activity", "wave"),
    "绩效": ("award", "trophy", "chart", "gauge", "target", "trending"),
    "客户": ("user", "users", "handshake", "heart", "briefcase", "building"),
    "用户": ("user", "users", "person", "account", "face"),
    "团队": ("users", "group", "team", "user", "handshake"),
    "组织": ("sitemap", "hierarchy", "building", "users", "network"),
    "协作": ("handshake", "users", "messages", "share", "arrows"),
    "伙伴": ("handshake", "users", "heart", "building"),
    "人员": ("user", "users", "person", "id", "badge"),
    "流程": ("route", "arrows", "git", "branch", "timeline", "refresh", "arrow"),
    "步骤": ("list", "numbers", "arrow", "route", "stairs", "steps"),
    "闭环": ("refresh", "repeat", "recycle", "arrows", "circle"),
    "分支": ("git", "branch", "fork", "arrows", "route"),
    "路径": ("route", "map", "navigation", "compass", "arrow"),
    "时间": ("clock", "calendar", "hourglass", "timer", "history"),
    "周期": ("calendar", "clock", "refresh", "repeat", "hourglass"),
    "里程碑": ("flag", "milestone", "trophy", "calendar", "pin", "target"),
    "进度": ("progress", "loader", "clock", "timeline", "chart", "checklist"),
    "计划": ("calendar", "clipboard", "checklist", "map", "compass"),
    "日程": ("calendar", "clock", "alarm", "event"),
    "效率": ("bolt", "rocket", "gauge", "zap", "speed", "flash"),
    "速度": ("bolt", "rocket", "gauge", "speed", "run"),
    "数据": ("database", "table", "chart", "analytics", "server", "binary"),
    "数据库": ("database", "server", "storage", "table"),
    "报表": ("report", "chart", "file", "table", "analytics"),
    "看板": ("dashboard", "layout", "kanban", "chart", "columns"),
    "分析": ("chart", "analytics", "search", "microscope", "graph", "report"),
    "洞察": ("bulb", "eye", "sparkles", "search", "brain", "telescope"),
    "系统": ("server", "cpu", "settings", "layers", "stack", "network"),
    "架构": ("layers", "stack", "sitemap", "hierarchy", "components", "building"),
    "平台": ("stack", "layers", "apps", "cloud", "server", "box"),
    "云端": ("cloud", "server", "network", "upload"),
    "云": ("cloud", "server"),
    "服务器": ("server", "database", "cpu", "rack"),
    "接口": ("api", "plug", "webhook", "link", "code"),
    "集成": ("plug", "puzzle", "components", "layers", "link"),
    "网络": ("network", "world", "globe", "wifi", "router", "share"),
    "智能": ("brain", "sparkles", "robot", "cpu", "wand"),
    "人工智能": ("brain", "robot", "sparkles", "cpu", "ai"),
    "算法": ("cpu", "code", "binary", "math", "brain", "function"),
    "模型": ("cube", "brain", "layers", "box", "3d", "network"),
    "自动化": ("robot", "settings", "cog", "automation", "bolt", "wand"),
    "机器人": ("robot", "bot", "cpu"),
    "产品": ("box", "package", "cube", "shopping", "gift", "apps"),
    "方案": ("bulb", "blueprint", "compass", "clipboard", "file", "puzzle"),
    "模块": ("components", "puzzle", "box", "cube", "blocks", "layout"),
    "工具": ("tool", "tools", "wrench", "hammer", "settings"),
    "研发": ("code", "flask", "cpu", "terminal", "bulb", "tool"),
    "制造": ("building", "factory", "settings", "cog", "tool", "robot"),
    "工厂": ("building", "factory", "industry", "cog"),
    "生产": ("settings", "factory", "cog", "box", "package"),
    "风险": ("alert", "warning", "exclamation", "shield", "flame", "triangle"),
    "告警": ("alert", "bell", "warning", "exclamation", "siren"),
    "问题": ("help", "question", "alert", "bug", "exclamation"),
    "痛点": ("alert", "flame", "bolt", "exclamation", "cross"),
    "异常": ("alert", "bug", "exclamation", "warning", "ban"),
    "错误": ("x", "error", "bug", "alert", "ban"),
    "目标": ("target", "flag", "crosshair", "focus", "trophy", "star"),
    "战略": ("compass", "chess", "target", "map", "flag", "mountain"),
    "定位": ("map", "pin", "target", "crosshair", "compass", "location"),
    "核心": ("cpu", "atom", "diamond", "star", "target", "circle"),
    "重点": ("star", "pin", "bookmark", "flag", "target", "exclamation"),
    "决策": ("scale", "gavel", "compass", "route", "check", "target"),
    "方向": ("compass", "arrow", "arrows", "sign", "navigation", "route"),
    "沟通": ("message", "messages", "chat", "mail", "phone", "comment"),
    "反馈": ("message", "thumb", "star", "comment", "mail"),
    "会议": ("users", "video", "presentation", "calendar", "microphone"),
    "汇报": ("presentation", "chart", "report", "file", "screen"),
    "文档": ("file", "document", "notes", "book", "article", "clipboard"),
    "合同": ("file", "signature", "writing", "clipboard", "handshake", "stamp"),
    "协议": ("file", "handshake", "signature", "shield"),
    "审批": ("check", "stamp", "clipboard", "file", "signature"),
    "质量": ("award", "rosette", "badge", "check", "diamond", "shield"),
    "标准": ("ruler", "scale", "certificate", "checklist", "award"),
    "认证": ("certificate", "badge", "rosette", "check", "shield"),
    "通过": ("check", "circle", "thumb", "badge"),
    "完成": ("check", "checklist", "flag", "circle"),
    "验证": ("check", "shield", "scan", "search", "fingerprint"),
    "渠道": ("broadcast", "share", "speakerphone", "store", "network", "route"),
    "营销": ("speakerphone", "megaphone", "ad", "target", "trending", "bullhorn"),
    "品牌": ("award", "crown", "star", "badge", "diamond", "tag"),
    "获客": ("user", "plus", "magnet", "target", "speakerphone"),
    "流量": ("activity", "wave", "trending", "users", "radar", "arrows"),
    "全球": ("world", "globe", "earth", "planet", "map"),
    "区域": ("map", "pin", "location", "compass", "building"),
    "门店": ("building", "store", "shop", "basket", "shopping"),
    "零售": ("shopping", "cart", "store", "shop", "tag", "receipt"),
    "电商": ("shopping", "cart", "bag", "credit", "store", "package"),
    "手机": ("device", "mobile", "phone", "smartphone"),
    "移动": ("device", "mobile", "phone", "arrows"),
    "应用": ("apps", "app", "device", "grid", "window"),
    "网页": ("browser", "world", "window", "code", "globe"),
    "桌面": ("device", "desktop", "laptop", "monitor", "screen"),
    "终端": ("terminal", "device", "desktop", "mobile", "screen"),
    "设备": ("device", "devices", "cpu", "hardware", "laptop"),
    "能源": ("bolt", "battery", "sun", "plug", "flame", "power"),
    "环保": ("leaf", "plant", "recycle", "tree", "world"),
    "绿色": ("leaf", "plant", "tree", "recycle", "seedling"),
    "医疗": ("heart", "stethoscope", "hospital", "medical", "first", "pill"),
    "健康": ("heart", "heartbeat", "activity", "shield", "medical"),
    "教育": ("school", "book", "books", "certificate", "pencil"),
    "培训": ("school", "presentation", "book", "users", "chalkboard"),
    "知识": ("book", "books", "bulb", "brain", "library", "school"),
    "搜索": ("search", "zoom", "radar", "eye", "binoculars"),
    "筛选": ("filter", "funnel", "adjustments", "sliders"),
    "对比": ("scale", "arrows", "columns", "contrast", "vs", "diff"),
    "监控": ("eye", "activity", "radar", "dashboard", "device", "heartbeat"),
    "审计": ("search", "clipboard", "checklist", "file", "eye", "shield"),
    "服务": ("headset", "lifebuoy", "support", "bell", "heart", "tool"),
    "运营": ("settings", "activity", "dashboard", "chart", "users", "cog"),
    "增长": ("trending", "chart", "growth", "arrow", "graph", "rocket"),
    "创新": ("bulb", "sparkles", "rocket", "wand", "atom", "flame"),
    "连接": ("link", "plug", "network", "share", "arrows", "chain"),
    "分享": ("share", "send", "upload", "network"),
    "下载": ("download", "cloud", "file", "arrow"),
    "上传": ("upload", "cloud", "file", "arrow"),
    "设置": ("settings", "adjustments", "sliders", "cog", "tool"),
    "地图": ("map", "pin", "location", "compass", "route"),
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def normalize_words(value: str) -> list[str]:
    return WORD_RE.findall(value.lower().replace("-", " ").replace("_", " "))


def _unique_preserve(items: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in items if item))


def read_svg_metadata(path: Path) -> tuple[str | None, list[str], str]:
    try:
        raw = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None, [], ""
    viewbox = None
    try:
        root = ET.fromstring(raw)
        tag = SVG_NS_RE.sub("", root.tag)
        if tag.lower() == "svg":
            viewbox = root.get("viewBox")
    except ET.ParseError:
        pass
    tags: list[str] = []
    category = ""
    comment_match = COMMENT_RE.search(raw)
    if comment_match:
        header = comment_match.group(1)
        tags_match = TAGS_LINE_RE.search(header)
        if tags_match:
            for item in tags_match.group(1).split(","):
                cleaned = item.strip().strip("\"'")
                if cleaned:
                    tags.extend(normalize_words(cleaned))
        category_match = CATEGORY_LINE_RE.search(header)
        if category_match:
            category = category_match.group(1).strip().strip("\"'")
    return viewbox, _unique_preserve(tags), category


def read_svg_viewbox(path: Path) -> str | None:
    viewbox, _, _ = read_svg_metadata(path)
    return viewbox


def build_index(icons_root: str | Path, *, icons_root_label: str | None = None) -> dict[str, Any]:
    root = Path(icons_root)
    icons: list[dict[str, Any]] = []
    for svg_path in sorted([*root.glob("*/*.svg"), *root.glob("*.svg")]):
        library = svg_path.parent.name
        name = svg_path.stem
        icon_id = f"{library}/{name}"
        viewbox, tags, category = read_svg_metadata(svg_path)
        search_terms = _unique_preserve(
            [
                *normalize_words(f"{library} {name}"),
                *normalize_words(category),
                *tags,
            ]
        )
        entry: dict[str, Any] = {
            "icon_id": icon_id,
            "library": library,
            "name": name,
            "path": str(svg_path.relative_to(root)).replace("\\", "/"),
            "viewBox": viewbox,
            "search_terms": search_terms,
            "bytes": svg_path.stat().st_size,
        }
        if category:
            entry["category"] = category
        if tags:
            entry["tags"] = tags
        icons.append(entry)
    return {
        "schema": "cyberppt.icon_index.v1",
        "icons_root": icons_root_label if icons_root_label is not None else str(root),
        "icon_count": len(icons),
        "libraries": sorted({icon["library"] for icon in icons}),
        "icons": icons,
    }


def expand_query_terms(query: str) -> tuple[list[str], list[tuple[str, int]]]:
    """Return (direct_ascii_words, weighted_synonym_terms) from English and Chinese queries."""
    direct = _unique_preserve(normalize_words(query))
    synonym_weights: dict[str, int] = {}
    for zh_term in sorted(ZH_SYNONYMS, key=len, reverse=True):
        if zh_term in query:
            mapped = ZH_SYNONYMS[zh_term]
            for idx, en_term in enumerate(mapped):
                weight = max(2, 6 - idx)
                if weight > synonym_weights.get(en_term, 0):
                    synonym_weights[en_term] = weight
    return direct, list(synonym_weights.items())


def search_icons(
    index: dict[str, Any],
    query: str,
    *,
    library: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    direct_words, synonym_terms = expand_query_terms(query)
    if not direct_words and not synonym_terms:
        return []
    raw_slug = query.strip().lower().replace("_", "-").replace(" ", "-")
    results: list[tuple[int, dict[str, Any]]] = []
    for icon in index.get("icons", []):
        if not isinstance(icon, dict):
            continue
        if library and icon.get("library") != library:
            continue
        name = str(icon.get("name", "")).lower()
        name_words = set(normalize_words(name))
        haystack = set(icon.get("search_terms", []))
        tags = set(icon.get("tags", []))
        score = 0
        if raw_slug and name == raw_slug:
            score += 12
        for word in direct_words:
            if name == word:
                score += 10
            elif word in name_words:
                score += 6
            elif word in tags or word in haystack:
                score += 4
            elif word in name:
                score += 2
        for term, weight in synonym_terms:
            if name == term:
                score += weight * 3
            elif term in name_words:
                score += weight * 2
            elif term in tags or term in haystack:
                score += weight
            elif term in name:
                score += max(1, weight // 2)
        if score:
            results.append((score, icon))
    results.sort(key=lambda item: (-item[0], len(str(item[1].get("name", ""))), item[1].get("icon_id", "")))
    return [icon for _, icon in results[:limit]]


def sync_icon(icons_root: str | Path, output_root: str | Path, icon_id: str) -> Path:
    if "/" not in icon_id:
        raise ValueError("icon_id must use '<library>/<name>' format")
    library, name = icon_id.split("/", 1)
    root = Path(icons_root)
    source = (root / f"{name}.svg" if root.name == library
              else root / library / f"{name}.svg")
    if not source.exists():
        raise FileNotFoundError(f"Icon not found: {icon_id}")
    destination = Path(output_root) / library / source.name
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def load_index(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CyberPPT icon library helper.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    build = subparsers.add_parser("build-index", help="Build assets/icons/index.json.")
    build.add_argument("--icons-root", required=True)
    build.add_argument("--out", required=True)

    search = subparsers.add_parser("search", help="Search icon index by keyword.")
    search.add_argument("--index", required=True)
    search.add_argument("--query", required=True)
    search.add_argument("--library")
    search.add_argument("--limit", type=int, default=20)

    sync = subparsers.add_parser("sync", help="Copy one icon into a project icons folder.")
    sync.add_argument("--icons-root", required=True)
    sync.add_argument("--icon", required=True)
    sync.add_argument("--out-dir", required=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "build-index":
        index = build_index(args.icons_root)
        write_json(Path(args.out), index)
        print(json.dumps({"path": args.out, "icon_count": index["icon_count"]}, indent=2))
        return 0
    if args.command == "search":
        index = load_index(Path(args.index))
        results = search_icons(index, args.query, library=args.library, limit=args.limit)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0 if results else 1
    if args.command == "sync":
        destination = sync_icon(args.icons_root, args.out_dir, args.icon)
        print(json.dumps({"icon": args.icon, "path": str(destination)}, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
