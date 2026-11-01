import React, { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import * as api from '../api.js';

const DeckMasterContext = createContext(null);

export function DeckMasterProvider({ children }) {
  const [workspace, setWorkspace] = useState(null);
  const [connectionError, setConnectionError] = useState('');
  const [actionError, setActionError] = useState('');
  const [scene, setScene] = useState('overview');
  const [currentPage, setCurrentPage] = useState(null);
  const [drawer, setDrawer] = useState(null);
  const [drafts, setDrafts] = useState({});
  const [busy, setBusy] = useState({});
  const locks = useRef(new Set());
  const readId = useRef(0);
  const [downloadStatus, setDownloadStatus] = useState(null);
  const [buildResult, setBuildResult] = useState(null);
  const [galleryLayer, setGalleryLayer] = useState('original');
  const [galleryView, setGalleryView] = useState('grid');
  const [query, setQuery] = useState('');
  const [presentation, setPresentation] = useState(null);
  const [toast, setToast] = useState(null);
  const [theme, setTheme] = useState(() => {
    try { return localStorage.getItem('deck-master-theme') || 'light'; }
    catch { return 'light'; }
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('deck-master-theme', theme); } catch { /* Theme persistence is optional. */ }
  }, [theme]);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(null), 3400);
    return () => clearTimeout(timer);
  }, [toast]);

  const refresh = useCallback(async (signal) => {
    const id = ++readId.current;
    const incoming = await api.getDeck(signal);
    if (signal?.aborted || id !== readId.current) return incoming;
    setWorkspace(current => api.mergeWorkspace(current, incoming));
    setConnectionError('');
    return incoming;
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    let timer;
    const poll = async () => {
      try { await refresh(controller.signal); }
      catch (error) { if (!controller.signal.aborted) setConnectionError(error.message); }
      if (!controller.signal.aborted) timer = setTimeout(poll, 1500);
    };
    poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh]);

  const perform = async (key, work) => {
    if (locks.current.has(key)) return;
    locks.current.add(key);
    setBusy(value => ({ ...value, [key]: true }));
    setActionError('');
    try { await work(); }
    catch (error) { setActionError(error.message); }
    finally {
      locks.current.delete(key);
      setBusy(value => ({ ...value, [key]: false }));
    }
  };
  const acceptSave = (result) => {
    ++readId.current;
    setWorkspace(current => api.mergeWorkspace(current, { ...current, ...result }));
  };
  const reload = async () => {
    try { await refresh(); }
    catch (error) { setConnectionError(error.message); }
  };
  const pages = workspace?.deck.pages || [];
  const getPage = (id) => pages.find(page => page.id === id);
  const getPageNumStr = (id) => String(pages.findIndex(page => page.id === id) + 1).padStart(2, '0');
  const openPage = (id) => { setCurrentPage(id); setScene('page'); setDrawer(null); };
  const editPage = (id) => {
    const page = getPage(id);
    if (!page) return;
    setCurrentPage(id);
    setDrafts(value => value[id] ? value : { ...value, [id]: api.createDraft(page, workspace.version) });
    setDrawer('editor');
  };
  const updateDraft = (page) => setDrafts(value => ({ ...value, [page.id]: { ...value[page.id], page } }));
  const saveDraft = () => perform('save', async () => {
    const draft = drafts[currentPage];
    try {
      const result = await api.putDeck(draft.base, api.draftPatch(draft));
      acceptSave(result);
      setDrafts(value => { const next = { ...value }; delete next[draft.page.id]; return next; });
      setDrawer(null);
      setToast('正文与讲稿已保存');
      await reload();
    } catch (error) {
      if (error.status !== 409) throw error;
      setDrafts(value => ({ ...value, [draft.page.id]: { ...value[draft.page.id], conflict: error.data } }));
      await reload();
    }
  });
  const rebaseDraft = () => {
    setDrafts(value => ({ ...value, [currentPage]: { ...value[currentPage], base: workspace.version, conflict: null } }));
    setToast('已保留输入；请核对后再次保存');
  };
  const discardDraft = () => {
    setDrafts(value => { const next = { ...value }; delete next[currentPage]; return next; });
    setDrawer(null);
  };
  const createPage = () => perform('create', async () => {
    let n = 1;
    while (pages.some(page => page.id === `p${n}`)) n++;
    const id = `p${n}`;
    const result = await api.putDeck(workspace.version, { order: [...pages.map(page => page.id), id], pages: [{ id }] });
    acceptSave(result);
    const page = result.deck.pages.find(page => page.id === id);
    setDrafts(value => ({ ...value, [id]: api.createDraft(page, result.version) }));
    setCurrentPage(id);
    setScene('page');
    setDrawer('editor');
    await reload();
  });
  const stopRun = (id) => perform(`cancel-${id}`, async () => {
    const result = await api.cancelRun(id);
    ++readId.current;
    setWorkspace(current => ({ ...current, runs: current.runs.map(run => result.runs.find(item => item.id === run.id) || run) }));
    setToast('任务已停止，迟到结果仅保存');
    await reload();
  });
  const build = () => perform('build', async () => {
    const result = await api.buildDeck();
    setBuildResult(result);
    setDownloadStatus(result);
    setToast('PPTX 已构建，可下载');
    await reload();
  });
  const download = (format) => perform(`export-${format}`, async () => {
    const result = await api.exportDeck(format);
    setDownloadStatus(result.status);
    const url = URL.createObjectURL(result.blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = result.filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    setToast('已开始下载');
  });
  const restore = (version) => perform('restore', async () => {
    acceptSave(await api.restoreVersion(version));
    setToast('已恢复为新版本，历史和未保存输入仍保留');
    await reload();
  });

  return <DeckMasterContext.Provider value={{
    workspace, pages, revision: workspace?.version, activeProject: workspace?.deck.brief.title || '未命名作品',
    connectionError, actionError, busy, refresh: reload, scene, setScene, currentPage,
    getPage, getPageNumStr, openPage, editPage, createPage, drafts, updateDraft, saveDraft, rebaseDraft, discardDraft,
    drawer, openDrawer: setDrawer, closeDrawer: () => setDrawer(null),
    stopRun, build, buildResult, download, downloadStatus, restore,
    galleryLayer, setGalleryLayer, galleryView, setGalleryView, query, setQuery,
    presentation, setPresentation, toast, theme, toggleTheme: () => setTheme(value => value === 'dark' ? 'light' : 'dark'),
  }}>{children}</DeckMasterContext.Provider>;
}

export function useDeckMaster() {
  return useContext(DeckMasterContext);
}
