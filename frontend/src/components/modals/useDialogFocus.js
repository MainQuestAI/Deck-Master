import { useEffect, useRef } from 'react';

const FOCUSABLE = 'button:not(:disabled), input:not(:disabled), textarea:not(:disabled), select:not(:disabled), summary, a[href], [tabindex]:not([tabindex="-1"])';

export function trapDialogTab(dialog, event, active = document.activeElement) {
  if (event.key !== 'Tab') return;
  const controls = [...dialog.querySelectorAll(FOCUSABLE)];
  const first = controls[0];
  const last = controls.at(-1);
  if (!first) {
    event.preventDefault();
    dialog.focus();
    return;
  }
  if (event.shiftKey && (active === first || active === dialog || !dialog.contains(active))) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && (active === last || active === dialog || !dialog.contains(active))) {
    event.preventDefault();
    first.focus();
  }
}

export default function useDialogFocus(open, onClose) {
  const dialog = useRef(null);
  const close = useRef(onClose);
  close.current = onClose;

  useEffect(() => {
    if (!open || !dialog.current) return;
    const panel = dialog.current;
    const previous = document.activeElement;
    (panel.querySelector('[data-dialog-initial-focus]') || panel).focus();
    const keydown = event => {
      if (event.key === 'Escape') {
        event.preventDefault();
        close.current();
        return;
      }
      trapDialogTab(panel, event);
    };
    document.addEventListener('keydown', keydown);
    return () => {
      document.removeEventListener('keydown', keydown);
      previous?.focus?.({ preventScroll: true });
    };
  }, [open]);

  return dialog;
}
