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
  const [contextDrafts, setContextDrafts] = useState({ brief: null, framing: null });
  const [busy, setBusy] = useState({});
  const locks = useRef(new Set());
  const readId = useRef(0);
  const [downloadStatus, setDownloadStatus] = useState(null);
  const [buildResult, setBuildResult] = useState(null);
  const [galleryLayer, setGalleryLayer] = useState('original');
  const [galleryView, setGalleryView] = useState('grid');
  const [query, setQuery] = useState('');
  const [presentation, setPresentation] = useState(null);
  const [comparison, setComparison] = useState(null);
  // Removal can finish after the author has opened another page or comparison.
  const pageNavigation = useRef({ currentPage, comparison });
  useEffect(() => { pageNavigation.current = { currentPage, comparison }; }, [currentPage, comparison]);
  const [reviewDrafts, setReviewDrafts] = useState({});
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
    let retryDelay = 1500;
    const poll = async () => {
      let delay = 1500;
      try {
        await refresh(controller.signal);
        retryDelay = 1500;
      } catch (error) {
        if (!controller.signal.aborted) setConnectionError(`与本地服务断开，正在重试。${error.message}`);
        delay = retryDelay;
        retryDelay = Math.min(retryDelay * 2, 15000);
      }
      if (!controller.signal.aborted) timer = setTimeout(poll, delay);
    };
    poll();
    return () => { controller.abort(); clearTimeout(timer); };
  }, [refresh]);

  const perform = async (key, work) => {
    if (locks.current.has(key)) return;
    locks.current.add(key);
    setBusy(value => ({ ...value, [key]: true }));
    setActionError('');
    try { return await work(); }
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
    if (!page && !drafts[id]) return;
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
  const openContextEdit = (kind) => {
    setContextDrafts(value => {
      const draft = value[kind];
      if (draft && (draft.conflict || api.contextUnitPatch(kind, draft) !== null)) return value;
      return { ...value, [kind]: api.createContextDraft(workspace.deck[kind], workspace.version) };
    });
  };
  const updateContextDraft = (kind, next) => {
    setContextDrafts(value => ({ ...value, [kind]: { ...value[kind], value: next } }));
  };
  const refreshContextConflict = async (kind) => {
    try {
      const snapshot = await refresh();
      setContextDrafts(value => ({ ...value, [kind]: { ...value[kind], error: '', conflict: { ...value[kind].conflict, snapshot } } }));
    } catch (error) {
      setContextDrafts(value => ({ ...value, [kind]: { ...value[kind], error: error.message } }));
    }
  };
  const resolveContextConflict = (kind, keepMine) => {
    setContextDrafts(value => {
      const draft = value[kind];
      const snapshot = draft.conflict?.snapshot;
      if (!snapshot) return value;
      const next = api.createContextDraft(snapshot.deck[kind], snapshot.version);
      return { ...value, [kind]: keepMine ? { ...next, value: draft.value } : next };
    });
  };
  const saveContext = (kind) => perform(`save-${kind}`, async () => {
    const draft = contextDrafts[kind];
    const patch = api.contextUnitPatch(kind, draft);
    if (!patch || draft.conflict) return;
    setContextDrafts(value => ({ ...value, [kind]: { ...value[kind], error: '' } }));
    try {
      const result = await api.putDeck(draft.base, patch);
      acceptSave(result);
      setContextDrafts(value => ({ ...value, [kind]: api.createContextDraft(result.deck[kind], result.version) }));
      setToast(kind === 'brief'
        ? (result.deck.pages.length ? '任务信息已保存，可在当前 Codex 会话中据此调整正文' : '任务信息已保存')
        : (result.deck.pages.length ? '框架已修改；正文如需按新框架调整，请在当前 Codex 会话继续' : '框架已保存'));
      await reload();
    } catch (error) {
      setContextDrafts(value => ({ ...value, [kind]: { ...value[kind], error: error.status === 409 ? '' : error.message, conflict: error.status === 409 ? error.data : value[kind].conflict } }));
      if (error.status === 409) await refreshContextConflict(kind);
    }
  });
  const createPage = () => perform('create', async () => {
    const id = api.createPageId(pages, drafts);
    const result = await api.putDeck(workspace.version, { order: [...pages.map(page => page.id), id], pages: [{ id }] });
    acceptSave(result);
    const page = result.deck.pages.find(page => page.id === id);
    setDrafts(value => ({ ...value, [id]: api.createDraft(page, result.version) }));
    setCurrentPage(id);
    setScene('page');
    setDrawer('editor');
    await reload();
  });
  const savePageOrder = async (patch) => {
    try {
      const result = await api.putDeck(workspace.version, patch);
      acceptSave(result);
      return result;
    } catch (error) {
      if (error.status === 409) {
        setToast('页面或页序已变化，请核对最新内容后重新操作');
        await reload();
      }
      throw error;
    }
  };
  const movePage = (pageId, toIndex) => perform('page-order', async () => {
    const order = pages.map(page => page.id);
    const nextOrder = api.reorderPages(order, pageId, toIndex);
    if (nextOrder === order) return;
    await savePageOrder({ order: nextOrder });
    setToast('页序已保存');
    await reload();
    return true;
  });
  const removePage = (pageId) => perform('page-order', async () => {
    const index = pages.findIndex(page => page.id === pageId);
    if (index < 0) return;
    const result = await savePageOrder(api.removePagePatch(pages.map(page => page.id), pageId));
    const remaining = new Set(result.deck.pages.map(page => page.id));
    const neighbor = [...pages.slice(0, index).reverse(), ...pages.slice(index + 1)]
      .find(page => remaining.has(page.id))?.id || result.deck.pages[0]?.id || null;
    const navigation = pageNavigation.current;
    setCurrentPage(current => current === pageId ? neighbor : current);
    setPresentation(current => current === pageId ? null : current);
    setComparison(current => current?.pageId === pageId ? null : current);
    if (navigation.currentPage === pageId) setDrawer(null);
    setScene(current => (current === 'compare' && navigation.comparison?.pageId === pageId)
      || (['page', 'presentation'].includes(current) && navigation.currentPage === pageId && !neighbor) ? 'content' : current);
    setToast('已从当前稿件移除（历史仍保留）');
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
  const addReview = (text, pageId) => perform(`review-add-${pageId ? `page:${pageId}` : 'deck'}`, async () => {
    const review = await api.addReview(text, pageId);
    setReviewDrafts(value => ({ ...value, [pageId ? `page:${pageId}` : 'deck']: '' }));
    setToast('意见已保存');
    await reload();
    return review;
  });
  const resolveReview = (id) => perform(`review-resolve-${id}`, async () => {
    await api.resolveReview(id);
    setToast('意见已标记为已处理');
    await reload();
  });
  const compareCandidate = (run, result) => {
    const page = getPage(result.page_id);
    if (!page || !result.result_file) return;
    setComparison(api.comparisonSnapshot(run, result, page, workspace.version));
    setScene('compare');
  };
  const adoptCandidate = () => perform('adopt', async () => {
    await api.adoptCandidate(comparison.runId, comparison.pageId, comparison.candidateFile);
    setToast('候选已采用');
    await reload();
  });

  return <DeckMasterContext.Provider value={{
    workspace, pages, revision: workspace?.version, activeProject: workspace?.deck.brief.title || '未命名作品',
    connectionError, actionError, busy, refresh: reload, scene, setScene, currentPage,
    getPage, getPageNumStr, openPage, editPage, createPage, movePage, removePage, drafts, updateDraft, saveDraft, rebaseDraft, discardDraft,
    contextDrafts, openContextEdit, updateContextDraft, saveContext, refreshContextConflict, resolveContextConflict,
    drawer, openDrawer: setDrawer, closeDrawer: () => setDrawer(null),
    stopRun, build, buildResult, download, downloadStatus, restore,
    addReview, resolveReview, reviewDrafts, setReviewDrafts,
    comparison, compareCandidate, adoptCandidate,
    galleryLayer, setGalleryLayer, galleryView, setGalleryView, query, setQuery,
    presentation, setPresentation, toast, theme, toggleTheme: () => setTheme(value => value === 'dark' ? 'light' : 'dark'),
  }}>{children}</DeckMasterContext.Provider>;
}

export function useDeckMaster() {
  return useContext(DeckMasterContext);
}
