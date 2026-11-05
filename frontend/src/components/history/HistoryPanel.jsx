import React, { useEffect, useRef, useState } from 'react';
import { getVersion } from '../../api.js';
import { useDeckMaster } from '../../context/DeckMasterContext.jsx';
import HistoryList from './HistoryList.jsx';
import HistoryViewer from './HistoryViewer.jsx';
import HistoryCompare from './HistoryCompare.jsx';

export default function HistoryPanel() {
  const { workspace, busy, restore } = useDeckMaster();
  const [reading, setReading] = useState(null);
  const requestId = useRef(0);
  const retry = useRef(null);
  useEffect(() => () => { ++requestId.current; }, []);
  const history = workspace.history || [];
  const metadata = version => structuredClone(history.find(item => item.id === version) || null);

  const open = async (mode, leftVersion, rightVersion = workspace.version, rightFollowsCurrent = mode === 'compare' && rightVersion === workspace.version) => {
    const id = ++requestId.current;
    const leftMeta = metadata(leftVersion);
    const rightMeta = metadata(rightVersion);
    retry.current = () => open(mode, leftVersion, rightVersion, rightFollowsCurrent);
    setReading({ mode, leftVersion, rightVersion, rightFollowsCurrent, loading: true, error: '', left: null, right: null });
    try {
      const [left, right] = await Promise.all([
        getVersion(leftVersion), mode === 'compare' ? getVersion(rightVersion) : Promise.resolve(null),
      ]);
      if (id !== requestId.current) return;
      setReading({ mode, leftVersion, rightVersion, rightFollowsCurrent, left, right, leftMeta, rightMeta, loading: false, error: '' });
    } catch (error) {
      if (id === requestId.current) setReading(value => ({ ...value, loading: false, error: error.message }));
    }
  };

  const readSide = async (side, version, followsCurrent = version === workspace.version) => {
    const id = ++requestId.current;
    const meta = metadata(version);
    retry.current = () => readSide(side, version, followsCurrent);
    setReading(value => ({ ...value, [`${side}Version`]: version,
      rightFollowsCurrent: side === 'right' ? followsCurrent : value.rightFollowsCurrent, loading: true, error: '' }));
    try {
      const snapshot = await getVersion(version);
      if (id !== requestId.current) return;
      setReading(value => ({ ...value, [side]: snapshot, [`${side}Meta`]: meta, loading: false }));
    } catch (error) {
      if (id === requestId.current) setReading(value => ({ ...value, loading: false, error: error.message }));
    }
  };

  const back = () => { ++requestId.current; setReading(null); };
  const versionSelect = side => <label className="s4-field">
    <span>{side === 'left' ? (reading.mode === 'view' ? '阅读版本' : '左侧版本') : '右侧版本'}</span>
    <select disabled={reading.loading && !!reading.left} value={reading[`${side}Version`]} onChange={event => {
      const version = Number(event.target.value);
      if (reading.left && (reading.mode === 'view' || reading.right)) readSide(side, version);
      else open(reading.mode, side === 'left' ? version : reading.leftVersion, side === 'right' ? version : reading.rightVersion,
        side === 'right' ? version === workspace.version : reading.rightFollowsCurrent);
    }}>
      {!history.some(item => item.id === reading[`${side}Version`]) && <option value={reading[`${side}Version`]}>版本 {reading[`${side}Version`]}</option>}
      {history.map(item => <option key={item.id} value={item.id}>版本 {item.id} · {item.summary}</option>)}
    </select>
  </label>;

  if (!reading) return <HistoryList history={history} currentVersion={workspace.version} restoring={busy.restore}
    onView={version => open('view', version)} onCompare={version => open('compare', version)} onRestore={restore} />;
  return <div className="history-panel">
    <div className="history-actions">
      <button className="button" onClick={back}>返回历史列表</button>
      {reading.mode === 'view' && <button className="button" onClick={() => open('compare', reading.leftVersion)}>与当前稿对比</button>}
      <button className="button" disabled={busy.restore || reading.loading || !!reading.error || !reading.left || reading.left.version === workspace.version}
        onClick={() => restore(reading.left.version)}>整稿恢复到版本 {reading.left?.version ?? reading.leftVersion}</button>
    </div>
    <p>这里阅读和比较的是已保存版本，未保存输入仍保留。</p>
    <div className="history-columns">{versionSelect('left')}{reading.mode === 'compare' && versionSelect('right')}</div>
    {reading.mode === 'compare' && reading.rightFollowsCurrent && reading.right && workspace.version > reading.right.version && <div className="s4-message" role="status">
      当前稿件已更新至版本 {workspace.version}，可刷新右侧比较。
      <button className="button" disabled={reading.loading} onClick={() => readSide('right', workspace.version)}>刷新右侧比较</button>
    </div>}
    {reading.loading && <p role="status">正在读取版本正文…</p>}
    {reading.error && <div className="s4-message" role="alert">读取失败：{reading.error} <button className="button" onClick={() => retry.current()}>重试读取</button></div>}
    {reading.mode === 'view' && reading.left && <HistoryViewer snapshot={reading.left} meta={reading.leftMeta} />}
    {reading.mode === 'compare' && reading.left && reading.right && <HistoryCompare left={reading.left} right={reading.right} leftMeta={reading.leftMeta} rightMeta={reading.rightMeta} />}
  </div>;
}
