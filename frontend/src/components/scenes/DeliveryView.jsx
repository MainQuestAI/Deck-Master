import React from 'react';
import Icon from '../common/Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function DeliveryView() {
  const { openCompare, openDrawer, notify } = useDeckMaster();

  return (
    <div>
      <div className="view-head">
        <div>
          <h1>任务与交付</h1>
          <p>四大业务分区管理正在进行的后台流水、待处理决定、版本快照与审阅/交付文件。</p>
        </div>
        <div className="head-actions">
          <button
            className="primary"
            onClick={() => notify('已生成审阅包：企业内容运营方案_R08_Review.zip')}
          >
            <Icon name="download" />导出当前审阅包 (HTML/PDF)
          </button>
        </div>
      </div>

      {/* 4 Partitions Grid */}
      <div className="delivery-grid">
        <div>
          {/* Partition 1: In Progress */}
          <section className="delivery-section">
            <div className="row between">
              <h3>正在进行的任务</h3>
              <span className="badge ok pulse">1 运行中</span>
            </div>
            <div className="task-entry">
              <div>
                <strong style={{ fontSize: '14px' }}>第 13–15 页 · 原图候选生成</strong>
                <p className="muted" style={{ fontSize: '12px', marginTop: '4px' }}>
                  基于内容稿 R 08 · 提交时间 今天 10:18 · 结果已返回
                </p>
              </div>
              <button className="button tiny primary" onClick={() => openCompare(13)}>
                <Icon name="compare" />进入比对
              </button>
            </div>
            <div className="task-entry">
              <div>
                <strong style={{ fontSize: '14px' }}>第 09–12 页 · SVG 矢量转换流水</strong>
                <p className="muted" style={{ fontSize: '12px', marginTop: '4px' }}>
                  依赖原图已采用 · 等待任务发起
                </p>
              </div>
              <button
                className="button tiny"
                onClick={() => notify('已将第 09–12 页加入 SVG 矢量化流水队列。')}
              >
                <Icon name="arrow" />准备转换
              </button>
            </div>
          </section>

          {/* Partition 2: Pending Decisions */}
          <section className="delivery-section">
            <div className="row between">
              <h3>待决定的事项 (1)</h3>
              <span className="badge warn pulse">阻塞交付</span>
            </div>
            <div className="task-entry">
              <div>
                <strong>第 13 页原图候选 C 02 决策</strong>
                <p className="muted" style={{ fontSize: '12px', marginTop: '4px' }}>
                  采用后将生成新当前版本 R 09，历史版本保留。
                </p>
              </div>
              <button className="button tiny primary" onClick={() => openCompare(13)}>
                <Icon name="compare" />进行决策
              </button>
            </div>
          </section>

          {/* Partition 3: Versions Timeline */}
          <section className="delivery-section">
            <h3>版本记录与恢复基准</h3>
            <div className="task-entry">
              <div>
                <strong>当前工作版本 · R 08</strong>
                <p className="muted" style={{ fontSize: '12px', marginTop: '4px' }}>
                  今天 10:00 · 30 页结构完整 · 24 页已确认
                </p>
              </div>
              <span className="badge ok">当前活动基准</span>
            </div>
            <div className="task-entry">
              <div>
                <strong>历史版本 · R 07</strong>
                <p className="muted" style={{ fontSize: '12px', marginTop: '4px' }}>
                  昨天 17:30 · 调整第 3 章标题与论点
                </p>
              </div>
              <button
                className="button tiny"
                onClick={() => notify('已读取历史快照 R 07 (2026-10-22 17:30 只读视图)')}
              >
                <Icon name="read" />查看快照
              </button>
            </div>
            <div className="task-entry">
              <div>
                <strong>初始大纲版 · R 06</strong>
                <p className="muted" style={{ fontSize: '12px', marginTop: '4px' }}>
                  10月21日 · 初始录入 5 章节框架
                </p>
              </div>
              <button
                className="button tiny quiet"
                onClick={() => notify('已读取初始大纲快照 R 06 (2026-10-21 14:15 只读视图)')}
              >
                <Icon name="read" />查看
              </button>
            </div>
          </section>
        </div>

        {/* Partition 4: Delivery Packages & Export Gate */}
        <aside>
          <section className="delivery-section">
            <h3>交付文件包导出</h3>
            <p className="muted" style={{ fontSize: '12px', marginBottom: '18px', lineHeight: 1.6 }}>
              严格区分审阅包、最终交付包与工程恢复包，原因明示，不设模糊导出。
            </p>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div
                style={{
                  border: '1px solid var(--dm-color-border)',
                  borderRadius: 'var(--dm-radius-control)',
                  padding: '14px',
                  background: 'var(--dm-color-surface)'
                }}
              >
                <div className="row between">
                  <strong>01 审阅包 (Review)</strong>
                  <span className="badge ok">可用</span>
                </div>
                <p className="muted" style={{ fontSize: '12px', margin: '4px 0 12px' }}>
                  包含当前逐页稿、排版大图与来源清单。
                </p>
                <button
                  className="button tiny primary"
                  onClick={() => notify('已生成审阅包：企业内容运营方案_R08_Review.zip')}
                >
                  <Icon name="download" />下载审阅包 (ZIP)
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
                  <strong>02 正式交付包 (Delivery)</strong>
                  <span className="badge warn">不可用</span>
                </div>
                <p className="muted" style={{ fontSize: '12px', margin: '4px 0 12px' }}>
                  包含高清原图、SVG与可编辑幻灯片。
                </p>
                <button
                  className="button tiny"
                  disabled
                  title="前置检查发现 6 页待核对，导出已被阻止"
                >
                  <Icon name="download" />导出交付文件
                </button>
                <small style={{ display: 'block', color: 'var(--dm-color-danger)', marginTop: '8px' }}>
                  阻断原因：仍有 6 页正文未确认。
                </small>
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
                  <strong>03 工程恢复包 (Engineering)</strong>
                  <span className="badge neutral">内部工具</span>
                </div>
                <p className="muted" style={{ fontSize: '12px', margin: '4px 0 12px' }}>
                  JSON 数据模型与状态恢复快照。
                </p>
                <button
                  className="button tiny"
                  onClick={() => notify('已导出工程恢复数据快照 deck-master-snapshot-r08.json')}
                >
                  <Icon name="download" />导出工程备份
                </button>
              </div>
            </div>
          </section>
        </aside>
      </div>
    </div>
  );
}
