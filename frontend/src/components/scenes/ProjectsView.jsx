import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function ProjectsView() {
  const { setScene, setActiveProject, notify } = useDeckMaster();

  const handleSwitchProject = (name) => {
    setActiveProject(name);
    setScene('overview');
    notify(`已切换当前工作项目至：${name}`);
  };

  return (
    <div>
      <div className="view-head">
        <div>
          <h1>所有项目</h1>
          <p>选择要继续制作的商业表达方案，或基于新的业务目标创建项目。</p>
        </div>
        <div className="head-actions">
          <button
            className="primary"
            onClick={() => notify('进入短流程新建项目：任务说明 → 关联材料 → 保存位置 (前端样板演示)')}
          >
            <Icon name="plus" />
            新建项目
            <span className="badge neutral" style={{ fontSize: '10px', padding: '1px 5px', marginLeft: '4px' }}>
              演示
            </span>
          </button>
          <button
            className="button"
            onClick={() => notify('已触发系统文件夹选择器 (演示环境已连接本地目录)')}
          >
            <Icon name="folder" />
            打开本地目录
            <span className="badge neutral" style={{ fontSize: '10px', padding: '1px 5px', marginLeft: '4px' }}>
              本地
            </span>
          </button>
        </div>
      </div>

      <div className="project-list-grid">
        {/* Project 1: Active */}
        <div className="project-box" style={{ borderColor: 'var(--dm-color-action)' }}>
          <div>
            <div className="row between">
              <span className="badge ok pulse">当前打开</span>
              <small className="muted">最近打开 · 今天 10:14</small>
            </div>
            <h2 style={{ margin: '12px 0 6px' }}>企业内容运营方案</h2>
            <p className="muted" style={{ fontSize: '13px' }}>30 页 · 5 个章节 · 内容稿 R 08</p>
            <p style={{ marginTop: '10px', fontSize: '13px', color: 'var(--dm-color-text-secondary)', lineHeight: 1.6 }}>
              面向管理层汇报，24 页正文已确认，3 页原图候选待比较采用。
            </p>
          </div>
          <div className="row between" style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--dm-color-border-subtle)' }}>
            <span className="badge warn">3 页候选待核对</span>
            <button className="primary tiny" onClick={() => setScene('overview')}>
              <Icon name="arrow" />进入工作台
            </button>
          </div>
        </div>

        {/* Project 2: Archived */}
        <div className="project-box">
          <div>
            <div className="row between">
              <span className="badge neutral">已归档</span>
              <small className="muted">昨天 17:30</small>
            </div>
            <h2 style={{ margin: '12px 0 6px' }}>智能制造出海商业计划书</h2>
            <p className="muted" style={{ fontSize: '13px' }}>42 页 · 7 个章节 · 交付版本 V2</p>
            <p style={{ marginTop: '10px', fontSize: '13px', color: 'var(--dm-color-text-secondary)', lineHeight: 1.6 }}>
              全量 SVG 与可编辑幻灯片已导出，处于审阅锁定只读状态。
            </p>
          </div>
          <div className="row between" style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--dm-color-border-subtle)' }}>
            <span className="badge ok">交付检查通过</span>
            <button className="button tiny" onClick={() => handleSwitchProject('智能制造出海商业计划书')}>
              <Icon name="arrow" />打开此项目
            </button>
          </div>
        </div>

        {/* Project 3: In Progress */}
        <div className="project-box">
          <div>
            <div className="row between">
              <span className="badge warn">制作中</span>
              <small className="muted">10月21日</small>
            </div>
            <h2 style={{ margin: '12px 0 6px' }}>医疗大健康消费品新品上市 GTM</h2>
            <p className="muted" style={{ fontSize: '13px' }}>18 页 · 3 个章节 · 内容稿 R 04</p>
            <p style={{ marginTop: '10px', fontSize: '13px', color: 'var(--dm-color-text-secondary)', lineHeight: 1.6 }}>
              首批素材已匹配完成，正在执行第一阶段风格试作校准。
            </p>
          </div>
          <div className="row between" style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--dm-color-border-subtle)' }}>
            <span className="badge warn">2 项待决定</span>
            <button className="button tiny" onClick={() => handleSwitchProject('医疗大健康消费品新品上市 GTM')}>
              <Icon name="arrow" />打开此项目
            </button>
          </div>
        </div>

        {/* Project 4: Relocate / Path Invalid */}
        <div className="project-box disabled-project">
          <div>
            <div className="row between">
              <span className="badge danger">
                <Icon name="alert" />路径失效
              </span>
              <small className="muted">10月18日</small>
            </div>
            <h2 style={{ margin: '12px 0 6px', color: 'var(--dm-color-text-muted)' }}>2026 Q3 组织复盘报告</h2>
            <p className="muted" style={{ fontSize: '13px' }}>24 页 · 原项目目录已被移动</p>
            <p style={{ marginTop: '10px', fontSize: '13px', color: 'var(--dm-color-danger)', lineHeight: 1.6 }}>
              目标路径不可读，保留此入口与原因，不自动静默删除。
            </p>
          </div>
          <div className="row between" style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--dm-color-border-subtle)' }}>
            <button
              className="button tiny"
              onClick={() => notify('已重新核对本地文件系统路径，目录尚未就绪 (待联调后端)')}
            >
              <Icon name="folder" />重新定位目录
              <span className="badge neutral" style={{ fontSize: '9px', padding: '0 4px', marginLeft: '3px' }}>待联调</span>
            </button>
            <button
              className="button tiny quiet"
              onClick={(e) => {
                e.currentTarget.closest('.project-box').style.display = 'none';
                notify('已从历史记录中移除该项目条目。');
              }}
            >
              <Icon name="close" />移除记录
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
