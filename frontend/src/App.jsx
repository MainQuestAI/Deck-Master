import React from 'react';
import Reviewbar from './components/layout/Reviewbar';
import Sidebar from './components/layout/Sidebar';
import Topbar from './components/layout/Topbar';
import OverviewView from './components/scenes/OverviewView';
import ContentView from './components/scenes/ContentView';
import GalleryView from './components/scenes/GalleryView';
import DeliveryView from './components/scenes/DeliveryView';
import PageReaderView from './components/scenes/PageReaderView';
import DrawerPanel from './components/modals/DrawerPanel';
import PresentationModal from './components/modals/PresentationModal';
import Toast from './components/common/Toast';
import { useDeckMaster } from './context/DeckMasterContext';

export default function App() {
  const { scene, workspace, connectionError, actionError, refresh } = useDeckMaster();
  const scenes = { overview: OverviewView, content: ContentView, gallery: GalleryView, delivery: DeliveryView, page: PageReaderView };
  const Scene = scenes[scene] || OverviewView;
  return <>
    <a className="skip-link" href="#main-view">跳至主要工作区内容</a>
    <Reviewbar />
    <div className="app-shell">
      <Sidebar />
      <main className="content-area" id="main-view" tabIndex="-1">
        <Topbar />
        <div className="workspace-view">
          {connectionError && <div className="s4-message" role="alert">{connectionError} <button onClick={refresh}>重新连接</button></div>}
          {actionError && <div className="s4-message" role="alert">{actionError}</div>}
          {workspace ? <Scene /> : <p role="status">{connectionError ? '作品尚未加载' : '正在读取作品…'}</p>}
        </div>
      </main>
    </div>
    <DrawerPanel />
    <PresentationModal />
    <Toast />
  </>;
}
