import React, { useEffect } from 'react';
import Reviewbar from './components/layout/Reviewbar';
import Sidebar from './components/layout/Sidebar';
import Topbar from './components/layout/Topbar';
import ProjectsView from './components/scenes/ProjectsView';
import OverviewView from './components/scenes/OverviewView';
import ContentView from './components/scenes/ContentView';
import GalleryView from './components/scenes/GalleryView';
import StyleView from './components/scenes/StyleView';
import DeliveryView from './components/scenes/DeliveryView';
import PageReaderView from './components/scenes/PageReaderView';
import CompareView from './components/scenes/CompareView';
import PresentationModal from './components/modals/PresentationModal';
import SpotlightModal from './components/modals/SpotlightModal';
import DrawerPanel from './components/modals/DrawerPanel';
import Toast from './components/common/Toast';
import { useDeckMaster } from './context/DeckMasterContext';

export default function App() {
  const {
    scene,
    spotlightOpen,
    setSpotlightOpen,
    drawer,
    closeDrawer,
    presentation,
    exitPresentation,
    startPresentation,
    presNext,
    presPrev,
    togglePresThumbnails,
    togglePresAutoPlay,
    currentPage,
    movePage
  } = useDeckMaster();

  // Global Keyboard Shortcuts
  useEffect(() => {
    const handleKeyDown = (e) => {
      // 1. Presentation mode shortcuts
      if (presentation.open) {
        if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown') {
          e.preventDefault();
          presNext();
          return;
        }
        if (e.key === 'ArrowLeft' || e.key === 'PageUp') {
          e.preventDefault();
          presPrev();
          return;
        }
        if (e.key === 'Escape') {
          e.preventDefault();
          exitPresentation();
          return;
        }
        if (e.key.toLowerCase() === 't') {
          e.preventDefault();
          togglePresThumbnails();
          return;
        }
        if (e.key.toLowerCase() === 'p') {
          e.preventDefault();
          togglePresAutoPlay();
          return;
        }
        return;
      }

      // 2. 'P' key to start presentation in gallery or page
      if (
        !e.metaKey &&
        !e.ctrlKey &&
        !e.altKey &&
        e.key.toLowerCase() === 'p' &&
        !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)
      ) {
        if (scene === 'gallery' || scene === 'page') {
          e.preventDefault();
          startPresentation(currentPage || 1);
          return;
        }
      }

      // 3. Command+K / Ctrl+K
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setSpotlightOpen((prev) => !prev);
        return;
      }

      // 4. Escape to close drawers or spotlight
      if (e.key === 'Escape') {
        if (spotlightOpen) {
          e.preventDefault();
          setSpotlightOpen(false);
          return;
        }
        if (drawer) {
          e.preventDefault();
          closeDrawer();
          return;
        }
      }

      // 5. Alt + ArrowUp / ArrowDown for moving rows in S02
      if (e.altKey && ['ArrowUp', 'ArrowDown'].includes(e.key)) {
        const row = document.activeElement?.closest?.('.page-item-row');
        if (row && row.id?.startsWith('row-')) {
          e.preventDefault();
          const id = Number(row.id.replace('row-', ''));
          movePage(id, e.key === 'ArrowUp' ? -1 : 1);
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [
    presentation.open,
    scene,
    spotlightOpen,
    drawer,
    currentPage,
    presNext,
    presPrev,
    exitPresentation,
    startPresentation,
    togglePresThumbnails,
    togglePresAutoPlay,
    setSpotlightOpen,
    closeDrawer,
    movePage
  ]);

  const renderCurrentScene = () => {
    switch (scene) {
      case 'projects':
        return <ProjectsView />;
      case 'overview':
        return <OverviewView />;
      case 'content':
        return <ContentView />;
      case 'gallery':
        return <GalleryView />;
      case 'style':
        return <StyleView />;
      case 'delivery':
        return <DeliveryView />;
      case 'page':
        return <PageReaderView />;
      case 'compare':
        return <CompareView />;
      default:
        return <OverviewView />;
    }
  };

  return (
    <>
      <a className="skip-link" href="#main-view">跳至主要工作区内容</a>

      {/* Top Review Bar */}
      <Reviewbar />

      <div className="app-shell">
        {/* Left Sidebar */}
        <Sidebar />

        {/* Right Main Content Area */}
        <main className="content-area" id="main-view" tabIndex="-1">
          <Topbar />
          <div className="workspace-view" id="workspace-mount">
            {renderCurrentScene()}
          </div>
        </main>
      </div>

      {/* Modals & Overlays */}
      <DrawerPanel />
      <PresentationModal />
      <SpotlightModal />
      <Toast />
    </>
  );
}
