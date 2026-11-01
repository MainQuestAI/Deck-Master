import React, { createContext, useContext, useState, useEffect, useCallback, useMemo } from 'react';
import { initialPages, initialCandidateDiffData, initialAnnotations, chapters } from '../constants/data';

const DeckMasterContext = createContext(null);

export function DeckMasterProvider({ children }) {
  const [theme, setTheme] = useState(() => {
    try {
      return localStorage.getItem('deck-master-theme') || 'light';
    } catch {
      return 'light';
    }
  });

  const [scene, setScene] = useState('overview');
  const [activeProject, setActiveProject] = useState('企业内容运营方案');
  const [contentTab, setContentTab] = useState('structure'); // 'structure' | 'chapters' | 'materials'
  const [galleryView, setGalleryView] = useState('grid'); // 'grid' | 'continuous'
  const [galleryLayer, setGalleryLayer] = useState('original'); // 'original' | 'svg' | 'text'
  const [galleryFilter, setGalleryFilter] = useState('all'); // 'all' | 'original' | 'svg' | 'pending'
  const [stylePhase, setStylePhase] = useState(2); // 1..4
  const [deliveryTab, setDeliveryTab] = useState('tasks');
  const [pageView, setPageView] = useState('read'); // 'read' | 'preview'
  const [pageLayer, setPageLayer] = useState('text'); // 'text' | 'original' | 'svg'
  const [currentPage, setCurrentPage] = useState(16);
  const [chapterFilter, setChapterFilter] = useState(-1);
  const [query, setQuery] = useState('');
  const [filter, setFilter] = useState('all'); // 'all' | 'candidate' | 'review' | 'svg-ready'
  const [selected, setSelected] = useState(() => new Set());
  
  const [pages, setPages] = useState(initialPages);
  const [order, setOrder] = useState(() => initialPages.map(p => p.id));
  const [savedOrder, setSavedOrder] = useState(() => initialPages.map(p => p.id));
  const [orderDirty, setOrderDirty] = useState(false);
  
  const [notes, setNotes] = useState({});
  const [revision, setRevision] = useState(8);
  const [editorWide, setEditorWide] = useState(false);
  const [drawer, setDrawer] = useState(null);
  const [drawerExtra, setDrawerExtra] = useState({});
  const [spotlightOpen, setSpotlightOpen] = useState(false);
  const [spotlightQuery, setSpotlightQuery] = useState('');
  
  const [canvasGuides, setCanvasGuides] = useState({
    safeArea: true,
    thirds: false,
    grid: false
  });
  
  const [compareMode, setCompareMode] = useState('side-by-side'); // 'side-by-side' | 'curtain'
  const [compareCurtainPos, setCompareCurtainPos] = useState(50);
  const [candidateDiffData, setCandidateDiffData] = useState(initialCandidateDiffData);
  
  const [presentation, setPresentation] = useState({
    open: false,
    pageId: 16,
    showThumbnails: false,
    layer: 'original',
    autoPlay: false
  });
  
  const [activeCommentBlock, setActiveCommentBlock] = useState(null);
  const [annotations, setAnnotations] = useState(initialAnnotations);
  const [toast, setToast] = useState(null);

  // Apply theme to document element
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    try {
      localStorage.setItem('deck-master-theme', theme);
    } catch {}
  }, [theme]);

  // Toast notification helper
  const notify = useCallback((msg) => {
    setToast(msg);
    const timer = setTimeout(() => {
      setToast((curr) => (curr === msg ? null : curr));
    }, 3400);
    return () => clearTimeout(timer);
  }, []);

  // Theme toggle
  const toggleTheme = useCallback(() => {
    setTheme(prev => {
      const next = prev === 'dark' ? 'light' : 'dark';
      notify(next === 'dark' ? '已切换至 Pro Darkroom 暗室沉浸放映质感' : '已切换至 Studio Light 工作室明亮质感');
      return next;
    });
  }, [notify]);

  // Page lookup helper
  const getPage = useCallback((id) => pages.find(p => p.id === Number(id)), [pages]);

  // Page index helper
  const getPageNumStr = useCallback((id) => {
    const idx = order.indexOf(Number(id));
    return String(idx + 1).padStart(2, '0');
  }, [order]);

  // Move page up or down
  const movePage = useCallback((id, direction) => {
    const p = getPage(id);
    if (!p) return;
    const curIdx = order.indexOf(p.id);
    const targetIdx = curIdx + direction;
    if (targetIdx < 0 || targetIdx >= order.length) return;
    
    const targetPage = getPage(order[targetIdx]);
    if (!targetPage || targetPage.chapter !== p.chapter) return;
    
    setOrder(prevOrder => {
      const newOrder = [...prevOrder];
      [newOrder[curIdx], newOrder[targetIdx]] = [newOrder[targetIdx], newOrder[curIdx]];
      setOrderDirty(newOrder.some((x, i) => x !== savedOrder[i]));
      return newOrder;
    });
    notify(`已将第 ${curIdx + 1} 页调整为第 ${targetIdx + 1} 页`);
  }, [getPage, order, savedOrder, notify]);

  // Apply order
  const applyOrder = useCallback(() => {
    setSavedOrder([...order]);
    setOrderDirty(false);
    setDrawer(null);
    notify('页序调整已应用到样页。');
  }, [order, notify]);

  // Undo order
  const undoOrder = useCallback(() => {
    setOrder([...savedOrder]);
    setOrderDirty(false);
    notify('已撤销本次页序调整。');
  }, [savedOrder, notify]);

  // Open Page
  const openPage = useCallback((id) => {
    setCurrentPage(Number(id));
    setPageLayer('text');
    setScene('page');
    setDrawer(null);
    setSpotlightOpen(false);
  }, []);

  // Open Compare
  const openCompare = useCallback((id) => {
    setCurrentPage(Number(id || candidateDiffData.pageId));
    setScene('compare');
    setDrawer(null);
    setSpotlightOpen(false);
  }, [candidateDiffData.pageId]);

  // Open Drawer
  const openDrawer = useCallback((panelType, extra = {}) => {
    setDrawer(panelType);
    setDrawerExtra(extra);
  }, []);

  const closeDrawer = useCallback(() => {
    setDrawer(null);
    setDrawerExtra({});
  }, []);

  // Save Page Renaming
  const saveRename = useCallback((id, newTitle) => {
    if (!newTitle.trim()) return;
    setPages(prev => prev.map(p => p.id === Number(id) ? { ...p, title: newTitle.trim() } : p));
    closeDrawer();
    notify('页名修改已应用。');
  }, [closeDrawer, notify]);

  // Save Page Note
  const savePageNote = useCallback((id, noteText) => {
    setNotes(prev => ({ ...prev, [id]: noteText.trim() }));
    closeDrawer();
    notify('本页调整意见草稿已保存。');
  }, [closeDrawer, notify]);

  // Save Editor Content
  const saveEditorContent = useCallback((id, { title, goal, body }) => {
    setPages(prev => prev.map(p => p.id === Number(id) ? {
      ...p,
      title: title ? title.trim() : p.title,
      goal: goal ? goal.trim() : p.goal,
      body: body !== undefined ? body.trim() : p.body
    } : p));
    closeDrawer();
    notify('正文修改已成功保存至当前样页。');
  }, [closeDrawer, notify]);

  // Candidate Adoption
  const adoptCandidate = useCallback(() => {
    setCandidateDiffData(prev => ({ ...prev, status: 'adopted' }));
    setPages(prev => prev.map(p => p.id === candidateDiffData.pageId ? {
      ...p,
      title: '把一次创作转化为可持续复用的企业生产闭环',
      body: candidateDiffData.candidateText,
      candidate: false,
      original: true
    } : p));
    setRevision(9);
    notify('已采用候选 C 02！基准已自动升级为 R 09。');
  }, [candidateDiffData, notify]);

  const keepCurrent = useCallback(() => {
    setCandidateDiffData(prev => ({ ...prev, status: 'kept' }));
    notify('已决定保留当前基准 R 08，候选已归档。');
  }, [notify]);

  // Comments / Annotations
  const submitComment = useCallback((blockId, { text, author, role }) => {
    if (!text.trim()) {
      notify('请输入批注内容');
      return;
    }
    const newComment = {
      id: 'c-' + Date.now(),
      author: author || '李凡',
      role: role || '业务架构师',
      time: '刚刚',
      text: text.trim(),
      status: 'pending',
      suggestedText: '',
      replies: []
    };
    setAnnotations(prev => ({
      ...prev,
      [blockId]: [...(prev[blockId] || []), newComment]
    }));
    notify('已发表段落审阅批注！');
  }, [notify]);

  const adoptComment = useCallback((blockId, commentId) => {
    setAnnotations(prev => {
      const list = prev[blockId] || [];
      const target = list.find(c => c.id === commentId);
      if (!target || !target.suggestedText) return prev;
      
      const updatedList = list.map(c => c.id === commentId ? { ...c, status: 'adopted' } : c);
      
      // Update page goal or body
      setPages(prevPages => prevPages.map(page => {
        if (page.id !== currentPage) return page;
        if (blockId.includes('goal')) {
          return { ...page, goal: target.suggestedText };
        } else if (blockId.includes('body')) {
          return { ...page, body: target.suggestedText };
        }
        return page;
      }));

      return { ...prev, [blockId]: updatedList };
    });
    notify('已采纳修改建议并更新正文！');
  }, [currentPage, notify]);

  const toggleResolveComment = useCallback((blockId, commentId) => {
    setAnnotations(prev => {
      const list = prev[blockId] || [];
      let resolvedNow = false;
      const updatedList = list.map(c => {
        if (c.id === commentId) {
          const nextStatus = c.status === 'resolved' ? 'pending' : 'resolved';
          resolvedNow = nextStatus === 'resolved';
          return { ...c, status: nextStatus };
        }
        return c;
      });
      notify(resolvedNow ? '已标记为已解决' : '已重新激活为待处理状态');
      return { ...prev, [blockId]: updatedList };
    });
  }, [notify]);

  const deleteComment = useCallback((blockId, commentId) => {
    setAnnotations(prev => ({
      ...prev,
      [blockId]: (prev[blockId] || []).filter(c => c.id !== commentId)
    }));
    notify('批注已删除');
  }, [notify]);

  // Presentation Mode
  const startPresentation = useCallback((pageId = 1) => {
    setPresentation({
      open: true,
      pageId: Number(pageId) || currentPage || 1,
      showThumbnails: false,
      layer: 'original',
      autoPlay: false
    });
    notify(`已进入第 ${String(order.indexOf(Number(pageId) || currentPage || 1) + 1).padStart(2, '0')} 页全屏放映预览模式 (按 Esc 退出，P 键自动放映)`);
  }, [currentPage, order, notify]);

  const exitPresentation = useCallback(() => {
    setPresentation(prev => ({ ...prev, open: false, autoPlay: false }));
    if (document.fullscreenElement) {
      document.exitFullscreen().catch(() => {});
    }
    notify('已退出放映预览模式');
  }, [notify]);

  const presNext = useCallback(() => {
    setPresentation(prev => {
      const currIdx = order.indexOf(prev.pageId);
      if (currIdx < order.length - 1) {
        return { ...prev, pageId: order[currIdx + 1] };
      }
      return prev;
    });
  }, [order]);

  const presPrev = useCallback(() => {
    setPresentation(prev => {
      const currIdx = order.indexOf(prev.pageId);
      if (currIdx > 0) {
        return { ...prev, pageId: order[currIdx - 1] };
      }
      return prev;
    });
  }, [order]);

  const togglePresThumbnails = useCallback(() => {
    setPresentation(prev => ({ ...prev, showThumbnails: !prev.showThumbnails }));
  }, []);

  const togglePresAutoPlay = useCallback(() => {
    setPresentation(prev => {
      const nextVal = !prev.autoPlay;
      notify(nextVal ? '已开启自动放映 (每 4.5 秒自动切页)' : '已停止自动放映');
      return { ...prev, autoPlay: nextVal };
    });
  }, [notify]);

  // Autoplay interval effect
  useEffect(() => {
    if (!presentation.open || !presentation.autoPlay) return;
    const interval = setInterval(() => {
      setPresentation(prev => {
        const currIdx = order.indexOf(prev.pageId);
        const nextId = currIdx < order.length - 1 ? order[currIdx + 1] : order[0];
        return { ...prev, pageId: nextId };
      });
    }, 4500);
    return () => clearInterval(interval);
  }, [presentation.open, presentation.autoPlay, order]);

  // Native Fullscreen toggle
  const toggleNativeFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
      notify('已切换至浏览器真全屏');
    } else {
      document.exitFullscreen().catch(() => {});
      notify('已退出全屏');
    }
  }, [notify]);

  // Selection handlers
  const toggleSelect = useCallback((id) => {
    setSelected(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const clearSelection = useCallback(() => {
    setSelected(new Set());
  }, []);

  // Guide toggle
  const toggleGuide = useCallback((guideName) => {
    setCanvasGuides(prev => {
      const nextVal = !prev[guideName];
      const names = { safeArea: '80% 安全区框线', thirds: '三分法构图网格', grid: '12列版心标尺' };
      notify(`已${nextVal ? '开启' : '关闭'}${names[guideName] || '参考线'}`);
      return { ...prev, [guideName]: nextVal };
    });
  }, [notify]);

  const value = useMemo(() => ({
    theme,
    toggleTheme,
    scene,
    setScene,
    activeProject,
    setActiveProject,
    contentTab,
    setContentTab,
    galleryView,
    setGalleryView,
    galleryLayer,
    setGalleryLayer,
    galleryFilter,
    setGalleryFilter,
    stylePhase,
    setStylePhase,
    deliveryTab,
    setDeliveryTab,
    pageView,
    setPageView,
    pageLayer,
    setPageLayer,
    currentPage,
    setCurrentPage,
    chapterFilter,
    setChapterFilter,
    query,
    setQuery,
    filter,
    setFilter,
    selected,
    toggleSelect,
    clearSelection,
    pages,
    order,
    savedOrder,
    orderDirty,
    movePage,
    applyOrder,
    undoOrder,
    notes,
    savePageNote,
    revision,
    editorWide,
    setEditorWide,
    drawer,
    drawerExtra,
    openDrawer,
    closeDrawer,
    saveRename,
    saveEditorContent,
    spotlightOpen,
    setSpotlightOpen,
    spotlightQuery,
    setSpotlightQuery,
    canvasGuides,
    toggleGuide,
    compareMode,
    setCompareMode,
    compareCurtainPos,
    setCompareCurtainPos,
    candidateDiffData,
    adoptCandidate,
    keepCurrent,
    presentation,
    setPresentation,
    startPresentation,
    exitPresentation,
    presNext,
    presPrev,
    togglePresThumbnails,
    togglePresAutoPlay,
    toggleNativeFullscreen,
    activeCommentBlock,
    setActiveCommentBlock,
    annotations,
    submitComment,
    adoptComment,
    toggleResolveComment,
    deleteComment,
    toast,
    notify,
    getPage,
    getPageNumStr,
    openPage,
    openCompare
  }), [
    theme, toggleTheme, scene, activeProject, contentTab, galleryView, galleryLayer,
    galleryFilter, stylePhase, deliveryTab, pageView, pageLayer, currentPage,
    chapterFilter, query, filter, selected, toggleSelect, clearSelection,
    pages, order, savedOrder, orderDirty, movePage, applyOrder, undoOrder,
    notes, savePageNote, revision, editorWide, drawer, drawerExtra, openDrawer,
    closeDrawer, saveRename, saveEditorContent, spotlightOpen, spotlightQuery,
    canvasGuides, toggleGuide, compareMode, compareCurtainPos, candidateDiffData,
    adoptCandidate, keepCurrent, presentation, startPresentation, exitPresentation,
    presNext, presPrev, togglePresThumbnails, togglePresAutoPlay, toggleNativeFullscreen,
    activeCommentBlock, annotations, submitComment, adoptComment, toggleResolveComment,
    deleteComment, toast, notify, getPage, getPageNumStr, openPage, openCompare
  ]);

  return (
    <DeckMasterContext.Provider value={value}>
      {children}
    </DeckMasterContext.Provider>
  );
}

export function useDeckMaster() {
  const context = useContext(DeckMasterContext);
  if (!context) {
    throw new Error('useDeckMaster must be used within a DeckMasterProvider');
  }
  return context;
}
