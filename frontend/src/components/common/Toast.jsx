import React from 'react';
import Icon from './Icon';
import { useDeckMaster } from '../../context/DeckMasterContext';

export default function Toast() {
  const { toast } = useDeckMaster();

  if (!toast) return null;

  return (
    <div
      id="toast-mount"
      className="toast-msg"
      role="status"
      aria-live="polite"
      style={{ display: 'flex' }}
    >
      <Icon name="check" />
      <span>{toast}</span>
    </div>
  );
}
