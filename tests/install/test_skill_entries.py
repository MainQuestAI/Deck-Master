"""Role entries stay independently addressable and share one method tree."""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SOURCE = REPO / "deck-skill"
ROLES = ("deck-master", "deck-content", "deck-design", "deck-review")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)")


def _local_links(text: str) -> list[str]:
    found = []
    for raw in LINK.findall(text):
        if raw.startswith(("http://", "https://", "mailto:")):
            continue
        path = raw.split("#", 1)[0]
        if path:
            found.append(path)
    return found


def _section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\s*$([\s\S]*?)(?=^## |\Z)", text, re.MULTILINE)
    assert match, heading
    return match[1]


def _has(text: str, *patterns: str) -> None:
    for pattern in patterns:
        assert re.search(pattern, text, re.DOTALL), pattern


def _frontmatter_name(path: Path) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    for line in lines[1:]:
        if line == "---":
            break
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip()
    raise AssertionError(f"missing name in {path}")


def test_source_has_four_real_manifests_and_unique_names() -> None:
    manifests = list(SOURCE.rglob("SKILL.md"))
    assert set(manifests) == {SOURCE / role / "SKILL.md" for role in ROLES}
    assert {_frontmatter_name(path) for path in manifests} == set(ROLES)
    assert not (SOURCE / "SKILL.md").exists()
    assert not list(SOURCE.glob("deck-*.md"))
    for path in manifests:
        assert path.is_file() and not path.is_symlink()


def test_role_entries_call_rust_deck() -> None:
    for role in ROLES:
        text = (SOURCE / role / "SKILL.md").read_text(encoding="utf-8")
        assert "`deck`" in text
        assert "deck_master" not in text
        assert "python -m deck_master" not in text
        assert "`deck-master " not in text
        for link in _local_links(text):
            assert link.startswith(("references/", "assets/"))


def test_shared_links_resolve_from_source_and_installed_directory(tmp_path: Path) -> None:
    install = tmp_path / "skills"
    install.mkdir()
    for role in ROLES:
        source = SOURCE / role
        directory = install / role
        directory.symlink_to(source, target_is_directory=True)
        for name in ("references", "assets"):
            assert (source / name).is_symlink()
            assert os.readlink(source / name) == f"../{name}"
            assert (directory / name).resolve() == SOURCE / name
        source_text = (source / "SKILL.md").read_text(encoding="utf-8")
        for link in _local_links(source_text):
            from_source = (source / link).resolve()
            assert from_source.exists()
            assert (directory / link).resolve() == from_source


def test_method_markdown_links_resolve() -> None:
    for path in SOURCE.rglob("*.md"):
        for link in _local_links(path.read_text(encoding="utf-8")):
            target = (path.parent / link).resolve()
            assert target.is_file() or target.is_dir(), f"{path} -> {link}"


@pytest.mark.parametrize("relative", ["deck-content/SKILL.md", "references/page-writing.md"])
def test_title_policy_preserves_page_roles(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    paragraphs = re.split(r"\n\s*\n", text)
    for role in ("说明", "教学"):
        policies = [p for p in paragraphs if re.search(rf"{role}(?:页|页面)", p)]
        assert any(
            "标题" in policy and "CTA" in policy
            and re.search(r"不(?:强制|要求|必)|无[需须]", policy)
            for policy in policies
        ), f"{relative}: {role} pages need title and CTA exceptions"
    assert re.search(r"判断页.{0,30}判断句", text)
    assert re.search(r"查阅页.{0,30}查阅职责", text)


@pytest.mark.parametrize("relative", ["deck-review/SKILL.md", "references/method-review.md"])
def test_review_guidance_separates_qa_layers(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    qa = _section(text, "三层 QA")
    _has(qa, r"Q1.*业务.*语义", r"Q2.*保真.*可读", r"Q3.*可编辑.*Office", r"独立")
    if relative == "deck-review/SKILL.md":
        assert "references/method-review.md#三层-qa" in LINK.findall(qa)
    else:
        _has(qa, r"不能.*(?:boolean|布尔)", r"status=pass.*不(?:等于|代表|证明)")
        _has(qa, r"visual_review", r"desktop_editing", r"not_evaluated", r"未执行")


def test_review_entry_requires_located_graded_evidence() -> None:
    entry = (SOURCE / "deck-review/SKILL.md").read_text(encoding="utf-8")
    report = _section(entry, "怎样返回")
    _has(report, r"页.*(?:对象|区域)", r"问题", r"影响", r"建议", r"分级", r"依据", r"原句", r"没有验证|未验证")
    method = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    grades = _section(method, "缺陷分级")
    for grade, example in (("Critical", "事实|数字"), ("Major", "主视觉|失真"), ("Minor", "位置|行距")):
        item = re.search(rf"`{grade}`([\s\S]*?)(?=^- |\Z)", grades, re.MULTILINE)
        assert item, grade
        _has(item[1], example)


def test_review_consumes_supported_readback_findings_without_inventing_edges() -> None:
    entry = (SOURCE / "deck-review/SKILL.md").read_text(encoding="utf-8")
    _has(entry, r"先.*findings.*再.*(?:阅图|画面)")
    method = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    documented = set(re.findall(r"`([a-z]+(?:_[a-z]+)+)`", method))
    codes = {
        "reversed_arrow", "missing_edge", "missing_node", "edge_not_connected",
        "unreadable_text", "hidden_or_tiny_text", "missing_visible_atom",
    }
    assert codes <= documented
    supported = set()
    for name in ("render.py", "readback_text.py", "readback_relations.py"):
        tree = ast.parse((REPO / "deck-tools/src/deck_tools" / name).read_text(encoding="utf-8"))
        supported.update(node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str))
    assert codes <= supported
    findings = _section(method, "机械发现与阅图定位")
    edges = next(line for line in findings.splitlines() if line.startswith("- 反箭头、漏分支："))
    _has(edges, r"(?:没有|缺少)预期边[^。]*(?:未检查|依据不足)")
    _has(edges, r"不从 layout[^。]*(?:解析|发明)边")
    guidance = findings.split("\n- ", 1)[0]
    _has(guidance, r"不(?:编造|发明) code")
    _has(_section(method, "三层 QA"), r"bbox.*pixel diff.*定位", r"不是唯一判断依据")


def test_review_requires_separate_blueprint_and_ppt_evidence() -> None:
    text = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    evidence = _section(text, "内容、主视觉与成品")
    for artifact in ("原图", "最终 PPT"):
        paragraphs = [p for p in re.split(r"\n\s*\n", evidence) if artifact in p]
        assert any("证据" in p and "未执行" in p for p in paragraphs), artifact
    _has(evidence, r"证据.*不能互相替代")


def test_review_protects_lookup_comparisons_and_synthetic_numbers() -> None:
    text = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    _has(text, r"查阅.*表.*(?:保留|保护)", r"E02.*同一.*口径", r"(?:合成|教学).*数字.*不能.*项目事实")


def test_master_turns_feedback_into_four_local_repair_paths() -> None:
    text = (SOURCE / "deck-master/SKILL.md").read_text(encoding="utf-8")
    routes = dict(re.findall(r"^- (内容|设计|调用|重建)：([\s\S]*?)(?=^-[ ]|^## |\Z)", text, re.MULTILINE))
    assert set(routes) == {"内容", "设计", "调用", "重建"}
    _has(routes["内容"], r"正文", r"purpose", r"layout", r"notes", r"deck put --base", r"不.*自动.*生图")
    _has(routes["设计"], r"主视觉", r"视觉计划", r"必要.*调用")
    _has(routes["调用"], r"需要新蓝图", r"deck run start image --pages", r"task.md.*原文", r"attachments.json")
    _has(routes["重建"], r"蓝图.*可用.*native-reconstruction.*plan", r"旧作品.*SVG", r"主结构.*蓝图.*重建")


def test_design_can_repair_plan_without_new_image() -> None:
    text = (SOURCE / "deck-design/SKILL.md").read_text(encoding="utf-8")
    production = _section(text, "主视觉与制作")
    _has(production, r"蓝图.*可用.*直接修该页 plan", r"需要新蓝图.*生图")
    steps = re.findall(r"^[12]\. (.+)$", production, re.MULTILINE)
    assert len(steps) == 2
    assert all("需要新蓝图时" in step for step in steps)
    _has(production, r"native/deck\.pptx", r"deck export pptx.*不包含")


def test_review_routes_submission_faults_separately_from_design() -> None:
    text = (SOURCE / "deck-review/SKILL.md").read_text(encoding="utf-8")
    report = _section(text, "怎样返回")
    _has(report, r"task.md.*附件.*正确", r"实际调用.*(?:改写|漏传).*交调用")
    _has(report, r"task.md.*原文", r"attachments.json.*提交", r"主视觉.*交设计")


def test_repair_rereview_links_to_existing_qa_judgments() -> None:
    text = (SOURCE / "deck-master/SKILL.md").read_text(encoding="utf-8")
    rereview = next(p for p in re.split(r"\n\s*\n", text) if "复审" in p)
    _has(rereview, r"只.*复审.*受影响.*范围")
    qa = next(link for link in LINK.findall(rereview) if link.startswith("references/method-review.md#"))
    path, anchor = qa.split("#", 1)
    method = (SOURCE / path).read_text(encoding="utf-8")
    heading = next(h for h in re.findall(r"^## (.+)$", method, re.MULTILINE) if h.lower().replace(" ", "-") == anchor)
    target = _section(method, heading)
    _has(target, r"Q1.*业务", r"Q2.*视觉", r"Q3.*Office", r"独立")


@pytest.mark.parametrize("relative", [
    "deck-content/SKILL.md", "deck-master/SKILL.md",
    "references/methods/M08-narrative.md", "references/page-writing.md",
])
def test_lookup_success_requires_reading_task_and_table_composition(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    success = next((p for p in re.split(r"\n\s*\n", text) if "留表才算成功" in p), "")
    assert all(token in success for token in ("阅读任务", "逐行核对", "构图句", "表是主视觉"))
    assert re.search(r"(?:只有|须|必须)[^。]*构图句[^。]*才算成功", success)
    if relative != "references/page-writing.md":
        assert re.search(r"主视觉选择[^。；]*阅读任务[^。；]*一致[^。；]*才算成功", success)
    assert "查阅页留表算成功" not in text
    assert "按构图句留表" not in text


def test_lookup_choice_uses_task_instead_of_keywords_or_drawing_ability() -> None:
    text = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
    criteria = next(p for p in re.split(r"\n\s*\n", text) if "评标矩阵" in p)
    _has(criteria, r"出现.*(?:不等于|不代表).*查阅页", r"能画成.*(?:不是.*留表.*理由|不(?:代表|意味着).*禁表|仍可留表)")
    _has(criteria, r"评标矩阵.*必须留表.*逐[行条]", r"不是封闭名单")
    _has(text, r"读者必须按行.*(?:勾选|定位|查找)", r"查阅职责.*标题.*不等于.*网格")


@pytest.mark.parametrize("relative", [
    "references/page-writing.md", "references/content-to-visual.md",
])
def test_declared_relations_require_body_rewrite_before_image_run(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    if relative.endswith("content-to-visual.md"):
        assert "page-writing.md#构图句写出本页的空间逻辑" in LINK.findall(text)
        text = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
    policy = next((p for p in re.split(r"\n\s*\n", text) if "不得再把表当主视觉" in p), "")
    assert re.search(r"`purpose`\s*或\s*`layout`", policy)
    assert all(relation in policy for relation in ("时间线", "交接", "状态流", "闭环"))
    assert re.search(r"正文[^；。]*按关系重组", policy)
    assert re.search(r"表[^；。]*最多[^；。]*取材", policy)
    assert re.search(r"先改[^；。]*构图句[^；。]*正文[^；。]*再调用[^；。]*run start image", policy)


@pytest.mark.parametrize("entry,chain", [
    ("references/methods/M08-narrative.md", ("../page-writing.md",)),
    ("deck-master/SKILL.md", ("references/page-writing.md",)),
    ("deck-content/SKILL.md", ("references/page-writing.md",)),
    ("deck-design/SKILL.md", ("references/content-to-visual.md", "page-writing.md")),
    ("deck-review/SKILL.md", ("references/method-review.md", "page-writing.md")),
])
def test_entry_methods_reach_shared_relation_constraint(entry: str, chain: tuple[str, ...]) -> None:
    path = SOURCE / entry
    for link in chain:
        text = path.read_text(encoding="utf-8")
        assert link in _local_links(text)
        path = path.parent / link
    shared = path.read_text(encoding="utf-8")
    assert "不得再把表当主视觉" in shared
    assert "run start image" in shared


@pytest.mark.parametrize("relative", ["references/page-writing.md", "deck-design/SKILL.md"])
def test_table_choice_is_not_a_title_or_block_type_ban(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    policy = next((line for line in text.splitlines() if "自动禁表" in line), "")
    assert all(title in policy for title in ("封面", "流程", "阶段", "计划", "分工"))
    assert re.search(r"不按[^。]*自动禁表", policy)
    writing = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
    assert re.search(r"`table`[^。]*不自动等于[^。]*画面[^。]*表格", writing)


def test_lookup_and_state_flow_examples_keep_their_distinct_jobs() -> None:
    text = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
    lookup_start = text.index("读者要按行找到要求、响应和展开位置")
    state, lookup = text[:lookup_start], text[lookup_start:]
    assert "原模块表仅作取材" in state
    assert "正文按关系重组" in state
    assert "无空位进入排队" in state
    assert "| 要求 | 响应要点 | 展开位置 |" in lookup
    assert "读者要按行找到要求、响应和展开位置" in lookup
    visual = (SOURCE / "references/content-to-visual.md").read_text(encoding="utf-8")
    assert re.search(r"查阅页[^；。]*逐行核对[^；。]*留表", visual)
    assert re.search(r"比较和查阅[^。]*可以[^。]*表为主视觉", visual)


def test_examples_distinguish_lookup_from_proof_and_operation() -> None:
    text = (SOURCE / "references/page-writing.md").read_text(encoding="utf-8")
    examples = re.findall(r"^- ([\s\S]*?)(?=^- |^## |\Z)", text, re.MULTILINE)
    for topic in ("验收：", "看板口径"):
        example = next(item for item in examples if topic in item)
        _has(example, r"(?:勾对|核对).*可留表", r"(?:过程|运转).*表不当主视觉")
    _has(text, r"例子.*不是封闭名单")
    example = next(p for p in re.split(r"\n\s*\n", text) if "交接清单" in p)
    _has(example, r"标题", r"逐[行条].*(?:勾对|核对)", r"layout.*表是主视觉.*可留表")


def test_review_routes_declared_relation_table_contradiction_to_design() -> None:
    text = (SOURCE / "references/method-review.md").read_text(encoding="utf-8")
    policy = next(p for p in re.split(r"\n\s*\n", text) if "查阅表为主视觉" in p)
    _has(policy, r"purpose", r"layout", r"选错主视觉.*交设计")
    assert "page-writing.md" in _local_links(policy)
    protection = next(p for p in re.split(r"\n\s*\n", text) if "不因是表格" in p)
    _has(protection, r"查阅.*保留查阅效率", r"不因.*表格.*判失败")


@pytest.mark.parametrize("entry", ["deck-design/SKILL.md", "deck-master/SKILL.md"])
def test_reconstruction_entries_share_object_preservation_rules(entry: str) -> None:
    text = (SOURCE / entry).read_text(encoding="utf-8")
    assert "references/native-reconstruction.md" in _local_links(text)
    native = (SOURCE / "references/native-reconstruction.md").read_text(encoding="utf-8")
    _has(native, r"坐标.*原图", r"不先造整套模板", r"图片面积不能超过画布的 40%", r"并排图.*一行结论")
    if entry == "deck-master/SKILL.md":
        assert "references/reconstruction.md" in _local_links(text)
        shared = (SOURCE / "references/reconstruction.md").read_text(encoding="utf-8")
        introduction = shared.split("\n## ", 1)[0]
        policy = next(p for p in re.split(r"\n\s*\n", introduction) if "重建依据" in p)
        _has(policy, r"原图.*对象和关系", r"不是.*正文块类型.*默认", r"说明文字.*不算还原")


def test_ui_annotations_keep_atoms_outside_and_controls_inside() -> None:
    ui = _section((SOURCE / "references/reconstruction.md").read_text(encoding="utf-8"), "界面原型")
    controls = next(p for p in re.split(r"\n\s*\n", ui) if "内部必须出现" in p)
    annotations = next(p for p in re.split(r"\n\s*\n", ui) if "分区说明" in p)
    _has(controls, r"内部必须出现[^。]*对应控件", r"不留空白线框")
    _has(annotations, r"外侧[^。]*标注[^。]*绑定[^。]*atom", r"内部[^。]*可编辑控件", r"不能[^。]*说明句[^。]*唯一内容")
    _has(annotations, r"不要求[^。]*拆成多个 atom", r"不改 atom 结构")


@pytest.mark.parametrize("relative", ["references/reconstruction.md", "references/visual-assets.md"])
def test_ui_nontext_assets_survive_with_editable_text_and_illustrative_status(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    if relative.endswith("reconstruction.md"):
        ui = _section(text, "界面原型")
    else:
        ui = text.split("\n## ", 1)[0]
    assets = next(p for p in re.split(r"\n\s*\n", ui) if "头像" in p)
    _has(assets, r"头像[^。]*SVG 子集[^。]*重画")
    _has(assets, r"有边界的局部 PNG/JPEG", r"asset add[^。]*image[^。]*引用")
    _has(assets, r"关键文字[^。]*可编辑", r"(?:生成或截取|截图或生成)[^。]*界面[^。]*示意属性")
    _has(assets, r"示意属性[^。]*不能冒充真实产品截图")
    if relative.endswith("reconstruction.md"):
        _has(ui, r"只有框架和关键字[^。]*不等于完成")
        _has(assets, r"先登记局部图[^。]*再准备 SVG 任务", r"补图[^。]*重新准备任务[^。]*attachments.json")
    else:
        _has(assets, r"只有框架和关键字[^。]*不等于完成", r"主正文[^。]*原生对象")
        selection = next(p for p in re.split(r"\n\s*\n", ui) if "选用前" in p)
        _has(selection, r"选用前[^。]*不得[^。]*删掉")
        assert "优先保留可编辑的关键文字与框架" not in text


def test_journeys_keep_spatial_order_and_action_scene_layer() -> None:
    text = _section((SOURCE / "references/reconstruction.md").read_text(encoding="utf-8"), "旅程与有方向的步骤")
    journey = next(p for p in re.split(r"\n\s*\n", text) if "原图是带人物或场景" in p)
    _has(journey, r"保留步骤的空间顺序", r"人物[^。]*动作[^。]*场景", r"重画[^。]*有边界的局部图")
    _has(journey, r"不能[^。]*模块卡片[^。]*除非原图")


def test_directional_paths_keep_nodes_and_connections_with_lookup_exception() -> None:
    text = _section((SOURCE / "references/reconstruction.md").read_text(encoding="utf-8"), "旅程与有方向的步骤")
    path = next(p for p in re.split(r"\n\s*\n", text) if "原图是横向" in p)
    _has(path, r"沿原图[^。]*节点边界[^。]*连线端点[^。]*方向[^。]*分支[^。]*回流")
    _has(path, r"不能[^。]*箭头[^。]*句子", r"没有空间方向[^。]*清单", r"只有原图[^。]*查阅清单[^。]*逐[行条]核对")
    lookup = next(p for p in re.split(r"\n\s*\n", text) if "查阅表本身" in p)
    _has(lookup, r"构图句[^。]*表是主视觉", r"purpose[^。]*layout[^。]*不得把表当主视觉", r"不按[^。]*标题[^。]*禁表")


def test_sentence_text_rule_cannot_collapse_multiple_visible_objects() -> None:
    text = (SOURCE / "references/svg-subset.md").read_text(encoding="utf-8")
    _has(text, r"句子型正文.*一个 text", r"保留完整句子", r"不在词中间硬折行")
    policy = next(p for p in re.split(r"\n\s*\n", text) if "多个可见对象" in p)
    _has(policy, r"多个入口", r"多个步骤节点", r"不要求.*整段塞进空框")
    _has(policy, r"外侧.*绑定原 atom", r"内侧重画.*可编辑文字", r"不要.*唯一一块字")


@pytest.mark.parametrize("relative", [
    "references/reconstruction.md", "references/method-review.md",
])
def test_reconstruction_acceptance_requires_actual_object_comparison(relative: str) -> None:
    text = (SOURCE / relative).read_text(encoding="utf-8")
    _has(text, r"实际打开.*预览.*原图", r"文字(?:回读|覆盖)", r"字符串齐全", r"(?:不能|未对照).*?(?:比对|对象|重建通过)")
    assert "重建未完成" in text
    if relative != "references/reconstruction.md":
        assert "reconstruction.md#对照原图验收" in LINK.findall(text)


def test_original_comparison_checks_screen_journey_and_path_objects() -> None:
    text = (SOURCE / "references/reconstruction.md").read_text(encoding="utf-8")
    acceptance = _section(text, "对照原图验收")
    for kind, behavior in (
        ("通用", r"阅读顺序.*说明文字"),
        ("界面原型", r"屏幕结构.*分区说明句"),
        ("顾客旅程", r"空间顺序.*人物动作或场景"),
        ("路径／步骤", r"连线端点.*对应对象"),
    ):
        item = re.search(rf"^- {kind}：([\s\S]*?)(?=^- |\Z)", acceptance, re.MULTILINE)
        assert item, kind
        _has(item[1], behavior)
    _has(acceptance, r"原图／编译预览对照", r"不新增自动视觉评分")
    _has(acceptance, r"visual_review", r"desktop_editing", r"not_evaluated", r"不能.*自动通过")


def test_reconstruction_retains_background_and_zero_picture_protections() -> None:
    text = _section((SOURCE / "references/reconstruction.md").read_text(encoding="utf-8"), "同时满足可编辑与画面保真")
    _has(text, r"禁止.*方便转 SVG.*扁平色块", r"禁止.*整页蓝图.*背景")
    _has(text, r"禁止.*pictures=0.*普通矩形", r"pictures=0.*不是目标.*不是失败", r"对象计数和图片数不能代表质量")
