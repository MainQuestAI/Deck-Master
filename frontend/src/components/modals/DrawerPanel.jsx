import React, { useState, useEffect } from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';
import { chapters } from '../../constants/data';

export default function DrawerPanel() {
  const {
    drawer,
    drawerExtra,
    closeDrawer,
    editorWide,
    setEditorWide,
    currentPage,
    getPage,
    getPageNumStr,
    saveEditorContent,
    saveRename,
    savePageNote,
    order,
    savedOrder,
    applyOrder,
    notes,
    setFilter,
    setScene,
    openCompare,
    notify
  } = useDeckMaster();

  // State for editor
  const page = getPage(drawerExtra.id || currentPage) || getPage(16);
  const [editTitle, setEditTitle] = useState('');
  const [editGoal, setEditGoal] = useState('');
  const [editBody, setEditBody] = useState('');
  const [renameVal, setRenameVal] = useState('');
  const [noteVal, setNoteVal] = useState('');

  useEffect(() => {
    if (page) {
      setEditTitle(page.title);
      setEditGoal(page.goal);
      setEditBody(page.body);
      setRenameVal(page.title);
      setNoteVal(notes[page.id] || '');
    }
  }, [page, notes, drawer]);

  if (!drawer) return null;

  let title = '';
  let bodyContent = null;
  let footContent = null;

  if (drawer === 'editor') {
    title = `修改第 ${getPageNumStr(page.id)} 页正文内容`;
    bodyContent = (
      <>
        <div className="form-group">
          <label htmlFor="edit-title-input">页面结论标题</label>
          <input
            type="text"
            id="edit-title-input"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor="edit-goal-input">核心目标与论证结论</label>
          <input
            type="text"
            id="edit-goal-input"
            value={editGoal}
            onChange={(e) => setEditGoal(e.target.value)}
          />
        </div>
        <div className="form-group">
          <label htmlFor="edit-body-textarea">正文与讲述段落</label>
          <textarea
            id="edit-body-textarea"
            rows={8}
            value={editBody}
            onChange={(e) => setEditBody(e.target.value)}
          />
          <small className="muted" id="edit-word-count">
            当前字数：{editBody.length} 字 · 实时保存生效中
          </small>
        </div>
        <div
          style={{
            background: 'var(--dm-color-surface-subtle)',
            padding: '16px',
            borderRadius: '6px',
            fontSize: '12px',
            marginTop: '18px'
          }}
        >
          <strong>关联来源事实</strong>
          <p className="muted" style={{ marginTop: '4px' }}>
            业务需求访谈纪要 §2 · 服务流程梳理规范
          </p>
        </div>
      </>
    );
    footContent = (
      <>
        <button className="button" onClick={() => setEditorWide((w) => !w)}>
          <Icon name={editorWide ? 'shrink' : 'expand'} />
          {editorWide ? '收起至 440px' : '展开至 880px 宽屏'}
        </button>
        <button className="button" onClick={closeDrawer}>
          <Icon name="close" />取消
        </button>
        <button
          className="primary"
          onClick={() => saveEditorContent(page.id, { title: editTitle, goal: editGoal, body: editBody })}
        >
          <Icon name="check" />保存并应用到样页
        </button>
      </>
    );
  } else if (drawer === 'source') {
    title = '页面关联材料依据详情';
    bodyContent = (
      <>
        <h3>业务需求访谈纪要 (第 2 节)</h3>
        <blockquote
          style={{
            margin: '12px 0',
            padding: '14px',
            background: 'var(--dm-color-surface-subtle)',
            borderLeft: '3px solid var(--dm-color-action)',
            fontSize: '13px',
            lineHeight: 1.7
          }}
        >
          “内容确认之后，设计和制作仍会反复沟通相同要求。希望每一次修改都能明确依据与受影响的页面范围，而不是推倒重来。”
        </blockquote>
        <h3 style={{ marginTop: '24px' }}>内容运营协作流程规范 (第 3 节)</h3>
        <blockquote
          style={{
            margin: '12px 0',
            padding: '14px',
            background: 'var(--dm-color-surface-subtle)',
            borderLeft: '3px solid var(--dm-color-action)',
            fontSize: '13px',
            lineHeight: 1.7
          }}
        >
          “候选结果必须与已锁定的页面目标和设计要求核对。通过固定基准比对决定是否采用，历史记录必须保留完整证据链。”
        </blockquote>
      </>
    );
    footContent = (
      <button className="button" onClick={closeDrawer}>
        <Icon name="close" />关闭
      </button>
    );
  } else if (drawer === 'rename') {
    title = `修改第 ${getPageNumStr(page.id)} 页页名`;
    bodyContent = (
      <>
        <div className="form-group">
          <label htmlFor="rename-input">新页名</label>
          <input
            type="text"
            id="rename-input"
            value={renameVal}
            onChange={(e) => setRenameVal(e.target.value)}
          />
        </div>
        <p className="muted" style={{ fontSize: '12px' }}>
          修改仅在当前样页中生效，不修改远端生产数据库。
        </p>
      </>
    );
    footContent = (
      <>
        <button className="button" onClick={closeDrawer}>
          <Icon name="close" />取消
        </button>
        <button
          className="primary"
          onClick={() => saveRename(page.id, renameVal)}
        >
          <Icon name="check" />确认修改
        </button>
      </>
    );
  } else if (drawer === 'order-review') {
    title = '预览页序调整与差异';
    const diffs = order
      .map((id, idx) => ({
        id,
        from: savedOrder.indexOf(id) + 1,
        to: idx + 1
      }))
      .filter((x) => x.from !== x.to);

    bodyContent = (
      <>
        <p className="muted" style={{ marginBottom: '16px' }}>
          以下为本次调序变动的页面，章节归属保持关联：
        </p>
        {diffs.length > 0 ? (
          diffs.map((d) => (
            <div
              key={d.id}
              style={{
                padding: '12px 0',
                borderBottom: '1px solid var(--dm-color-border-subtle)'
              }}
              className="row between"
            >
              <strong>{getPage(d.id)?.title}</strong>
              <span className="badge warn">第 {d.from} 页 → 第 {d.to} 页</span>
            </div>
          ))
        ) : (
          <p>尚未发现位置变动。</p>
        )}
      </>
    );
    footContent = (
      <>
        <button className="button" onClick={closeDrawer}>
          <Icon name="close" />继续调整
        </button>
        <button className="primary" onClick={applyOrder}>
          <Icon name="check" />应用本次页序
        </button>
      </>
    );
  } else if (drawer === 'todos') {
    title = '当前待处理事项清单';
    bodyContent = (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
        <div
          style={{
            border: '1px solid var(--dm-color-border)',
            borderRadius: 'var(--dm-radius-control)',
            padding: '14px',
            background: 'var(--dm-color-surface)'
          }}
        >
          <div className="row between">
            <strong>3 页原图候选待比对与采用</strong>
            <span className="badge warn pulse">待决定</span>
          </div>
          <p className="muted" style={{ fontSize: '12px', margin: '6px 0 12px' }}>
            第 13–15 页 · 生成结果已返回，需在并排工作台进行基准比对。
          </p>
          <button
            className="primary tiny"
            onClick={() => {
              closeDrawer();
              openCompare(13);
            }}
          >
            <Icon name="compare" />进入比对工作区
          </button>
        </div>

        <div
          style={{
            border: '1px solid var(--dm-color-border)',
            borderRadius: 'var(--dm-radius-control)',
            padding: '14px',
            background: 'var(--dm-color-surface)'
          }}
        >
          <div className="row between">
            <strong>6 页正文内容待最终确认</strong>
            <span className="badge warn">阻断交付</span>
          </div>
          <p className="muted" style={{ fontSize: '12px', margin: '6px 0 12px' }}>
            第 25–30 页 · 实施路径与验收章节，阶段范围需与管理层达成共识。
          </p>
          <button
            className="button tiny"
            onClick={() => {
              closeDrawer();
              setFilter('review');
              setScene('overview');
            }}
          >
            <Icon name="arrow" />筛选待确认页
          </button>
        </div>

        <div
          style={{
            border: '1px solid var(--dm-color-border)',
            borderRadius: 'var(--dm-radius-control)',
            padding: '14px',
            background: 'var(--dm-color-surface)'
          }}
        >
          <div className="row between">
            <strong>4 页可继续转换 SVG 矢量图</strong>
            <span className="badge ok">可执行</span>
          </div>
          <p className="muted" style={{ fontSize: '12px', margin: '6px 0 12px' }}>
            第 09–12 页 · 原图已通过采用，可直接进入矢量化流水。
          </p>
          <button
            className="button tiny"
            onClick={() => {
              closeDrawer();
              setFilter('svg-ready');
              setScene('overview');
            }}
          >
            <Icon name="file" />查看可转换页
          </button>
        </div>

        <div
          style={{
            border: '1px solid var(--dm-color-border)',
            borderRadius: 'var(--dm-radius-control)',
            padding: '14px',
            background: 'var(--dm-color-surface-subtle)'
          }}
        >
          <div className="row between">
            <strong>历史 1 次早期制作请求</strong>
            <span className="badge neutral">已接续</span>
          </div>
          <p className="muted" style={{ fontSize: '12px', marginTop: '6px' }}>
            旧失败已由新任务接续，记录保留归档，不阻断当前生产。
          </p>
        </div>
      </div>
    );
    footContent = (
      <button className="button" onClick={closeDrawer}>
        <Icon name="close" />关闭
      </button>
    );
  } else if (drawer === 'history') {
    title = '版本快照与变更历史';
    bodyContent = (
      <>
        <h3>当前活动基准 · 内容稿 R 08</h3>
        <p className="muted" style={{ fontSize: '12px', margin: '4px 0 16px' }}>
          今天 10:00 · 包含 30 页逐页稿、4 份关联材料依据。
        </p>
        <div
          style={{
            borderLeft: '3px solid var(--dm-color-action)',
            paddingLeft: '14px',
            marginBottom: '24px'
          }}
        >
          <strong>上一轮全稿检查发现已收敛</strong>
          <p style={{ fontSize: '13px', color: 'var(--dm-color-text-secondary)', marginTop: '4px' }}>
            已修正第 03 章中关于智能内容生产的核心表述，排版对齐 16:9 画板。
          </p>
        </div>

        <h3>历史版本归档</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', marginTop: '12px' }}>
          <div
            style={{
              padding: '12px 14px',
              background: 'var(--dm-color-surface-subtle)',
              borderRadius: 'var(--dm-radius-control)'
            }}
            className="row between"
          >
            <div>
              <strong>R 07 (上一稳定版)</strong>
              <small className="muted" style={{ display: 'block' }}>
                昨天 17:30 · 调整章节页序与标题
              </small>
            </div>
            <button
              className="button tiny"
              onClick={() => notify('已读取历史快照 R 07 (2026-10-22 17:30 只读视图)')}
            >
              <Icon name="read" />查看快照
            </button>
          </div>
          <div
            style={{
              padding: '12px 14px',
              background: 'var(--dm-color-surface-subtle)',
              borderRadius: 'var(--dm-radius-control)'
            }}
            className="row between"
          >
            <div>
              <strong>R 06 (大纲版)</strong>
              <small className="muted" style={{ display: 'block' }}>
                10月21日 · 初始 5 章节框架
              </small>
            </div>
            <button
              className="button tiny quiet"
              onClick={() => notify('已读取初始大纲快照 R 06 (2026-10-21 14:15 只读视图)')}
            >
              <Icon name="read" />查看
            </button>
          </div>
        </div>
      </>
    );
    footContent = (
      <button className="button" onClick={closeDrawer}>
        <Icon name="close" />关闭
      </button>
    );
  } else if (drawer === 'brief') {
    title = '企业内容运营方案 · 任务要求说明';
    bodyContent = (
      <>
        <h3>商业目标</h3>
        <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--dm-color-text-secondary)', margin: '8px 0 18px' }}>
          面向业务负责人与中台团队，阐明内容资产、生产协同与运营反馈的闭环体系。
          说明从一次性制作走向可持续内容资产经营的具体实施路径。
        </p>
        <h3>表达要求与约束</h3>
        <ul style={{ fontSize: '13px', lineHeight: 1.8, color: 'var(--dm-color-text-secondary)', paddingLeft: '20px' }}>
          <li>全篇 30 页，共 5 个章节，严密围绕管理层决策展开。</li>
          <li>数据与服务承诺在取得明确依据前不写为既定事实。</li>
          <li>视觉沿用中性桌面生产力规范，纯白底、深灰表面、无虚浮卡片与无意义渐变。</li>
        </ul>
      </>
    );
    footContent = (
      <button className="button" onClick={closeDrawer}>
        <Icon name="close" />关闭
      </button>
    );
  } else if (drawer === 'note') {
    title = `对第 ${getPageNumStr(page.id)} 页记录意见草稿`;
    bodyContent = (
      <>
        <p className="muted" style={{ fontSize: '12px', marginBottom: '14px' }}>
          意见仅保存在本地样页草稿中，用于当前阅读核对：
        </p>
        <div className="form-group">
          <label htmlFor="page-note-input">调整意见建议</label>
          <textarea
            id="page-note-input"
            rows={6}
            placeholder="例如：将第四个执行要点与业务访谈纪要中的审批节点对齐..."
            value={noteVal}
            onChange={(e) => setNoteVal(e.target.value)}
          />
        </div>
      </>
    );
    footContent = (
      <>
        <button className="button" onClick={closeDrawer}>
          <Icon name="close" />取消
        </button>
        <button
          className="primary"
          onClick={() => savePageNote(page.id, noteVal)}
        >
          <Icon name="check" />保存草稿
        </button>
      </>
    );
  } else if (drawer === 'argument') {
    title = '论证主线核对';
    bodyContent = (
      <>
        <p className="muted" style={{ fontSize: '12px', marginBottom: '18px' }}>
          5 个章节的核心推导逻辑如下：
        </p>
        {chapters.map((ch, i) => (
          <div
            key={i}
            style={{
              marginBottom: '14px',
              paddingBottom: '12px',
              borderBottom: '1px solid var(--dm-color-border-subtle)'
            }}
          >
            <strong>第 {i + 1} 章 · {ch}</strong>
            <p style={{ fontSize: '13px', color: 'var(--dm-color-text-secondary)', marginTop: '4px', lineHeight: 1.6 }}>
              {[
                '明确为何做、为谁服务以及当前素材分散痛点。',
                '建立可检索、可复用的内容资产底座与权限流转。',
                '用方案确认、制作、比较与采用贯通智能内容生产。',
                '将分发复盘与运营数据回写为团队知识资产。',
                '把整体规划转化为阶段范围、明确责任与可验收证据。'
              ][i]}
            </p>
          </div>
        ))}
      </>
    );
    footContent = (
      <button className="button" onClick={closeDrawer}>
        <Icon name="close" />关闭
      </button>
    );
  } else if (drawer === 'methods') {
    title = '方法与参考案例';
    bodyContent = (
      <>
        <h3>从业务决策倒推页面结构</h3>
        <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--dm-color-text-secondary)', margin: '8px 0 18px' }}>
          先明确本页要促成的管理层判断，再推导所需的论据、证据与版式关系，拒绝功能入口堆砌。
        </p>
        <h3>用对象关系表达生产流转</h3>
        <p style={{ fontSize: '14px', lineHeight: 1.7, color: 'var(--dm-color-text-secondary)', margin: '8px 0 18px' }}>
          在涉及确认、版本与交接时，清晰呈现页面、任务、候选与当前基准之间的演进关系。
        </p>
      </>
    );
    footContent = (
      <button className="button" onClick={closeDrawer}>
        <Icon name="close" />关闭
      </button>
    );
  } else if (drawer === 'style-preview') {
    title = '整稿风格基准规格';
    bodyContent = (
      <>
        <h3>浅色基准 S 01 · 供方案评审</h3>
        <blockquote
          style={{
            margin: '12px 0',
            padding: '14px',
            background: 'var(--dm-color-surface-subtle)',
            borderLeft: '3px solid var(--dm-color-action)',
            fontSize: '13px',
            lineHeight: 1.7
          }}
        >
          “16:9 宽屏画布；结论型标题优先；文字与图示基于 4px 基础网格；严禁纯文字 button；不把界面状态色带入正文内容。”
        </blockquote>
        <p style={{ fontSize: '13px', color: 'var(--dm-color-text-secondary)', marginTop: '16px' }}>
          完整参数与试作规范可在「S04 风格校准」工作台中实时查看与校验。
        </p>
      </>
    );
    footContent = (
      <button className="button" onClick={closeDrawer}>
        <Icon name="close" />关闭
      </button>
    );
  } else if (drawer === 'design') {
    title = 'Deck Master UI 重构与精修交互规格说明';
    bodyContent = (
      <>
        <h3>视觉美学与工匠级质感 (Awwwards / FWA / Webby Awards 标准)</h3>
        <p style={{ fontSize: '13px', lineHeight: 1.7, color: 'var(--dm-color-text-secondary)', margin: '8px 0 18px' }}>
          沿用 Deck-Master 的中性高密度设计基底，引入瑞士极简理性主义与次世代暗室放映双重质感支持，全量补齐 S00–S07 场景与 U01–U05 共享容器。
        </p>
        <h3>本轮顶级工匠级精修核心特性</h3>
        <ul style={{ fontSize: '13px', lineHeight: 1.85, color: 'var(--dm-color-text-secondary)', paddingLeft: '20px' }}>
          <li>
            <strong>双模式质感适配：</strong>顶栏支持「Studio Light (浅色工作室) / Pro Darkroom (暗室沉浸)」无缝切换，完全满足 WCAG AAA 级高对比标准。
          </li>
          <li>
            <strong>画板视效辅助系统：</strong>在 S04 风格校准与 S06 单页预览中，支持一键开关 80% 核心安全区、三分构图网格与 12 列版心标尺。
          </li>
          <li>
            <strong>S07 候选比对升级：</strong>支持「并排比对 (Side-by-Side)」与「卷帘滑块透视 (Split Slider)」双模式，无缝拖拽透视新旧排版差异。
          </li>
          <li>
            <strong>严禁纯文字 button 铁律：</strong>全界面 100% 按钮均配有表达操作语义的矢量图标，无任何遗漏。
          </li>
          <li>
            <strong>官方 C-refined-v1 紧凑标志：</strong>页眉嵌入官方 20×20 精确几何路径标志，绝对像素对齐。
          </li>
          <li>
            <strong>CJK 排印与字阶纪律：</strong>中文标题行高严格锁定 1.35–1.4，正文行高 1.7–1.8，英文大写标签增加 0.06em–0.08em 字间距。
          </li>
        </ul>
      </>
    );
    footContent = (
      <button className="button" onClick={closeDrawer}>
        <Icon name="close" />了解并返回
      </button>
    );
  } else {
    title = '信息面板';
    bodyContent = <p>操作已记录在当前原型会话中。</p>;
    footContent = (
      <button className="button" onClick={closeDrawer}>
        <Icon name="close" />关闭
      </button>
    );
  }

  return (
    <div
      className="drawer-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="drawer-title"
      onClick={closeDrawer}
    >
      <div
        className={`drawer-panel ${editorWide ? 'wide' : ''}`}
        onClick={(e) => e.stopPropagation()}
      >
        <header className="drawer-head">
          <h2 id="drawer-title" style={{ fontSize: '16px' }}>{title}</h2>
          <button
            className="button icon-only quiet"
            onClick={closeDrawer}
            aria-label="关闭抽屉"
          >
            <Icon name="close" />
          </button>
        </header>
        <div className="drawer-body">{bodyContent}</div>
        <footer className="drawer-foot">{footContent}</footer>
      </div>
    </div>
  );
}
