import { test } from 'node:test';
import assert from 'node:assert/strict';
import { trapDialogTab, presentationMove } from './useDialogFocus.js';

function dialogHarness(names) {
  const focused = [];
  const controls = names.map(name => ({
    name,
    disabled: false,
    focus() { focused.push(name); },
  }));
  const dialog = {
    contains: active => controls.includes(active),
    querySelectorAll: () => controls.filter(control => !control.disabled),
    focus() { focused.push('dialog'); },
  };
  return { controls, dialog, focused };
}

function tab(shiftKey = false) {
  return {
    key: 'Tab',
    shiftKey,
    prevented: false,
    preventDefault() { this.prevented = true; },
  };
}

test('presentation tab loop skips disabled previous and next controls', () => {
  const { controls, dialog, focused } = dialogHarness(['exit', 'previous', 'next']);
  const [exit, previous, next] = controls;
  previous.disabled = true;

  const backward = tab(true);
  trapDialogTab(dialog, backward, exit);
  assert.equal(backward.prevented, true);
  assert.deepEqual(focused, ['next']);

  focused.length = 0;
  const forward = tab();
  trapDialogTab(dialog, forward, next);
  assert.equal(forward.prevented, true);
  assert.deepEqual(focused, ['exit']);

  previous.disabled = false;
  next.disabled = true;
  focused.length = 0;
  trapDialogTab(dialog, tab(true), exit);
  assert.deepEqual(focused, ['previous']);
});

test('space advances the presentation except when a control already handles it', () => {
  const control = { closest: selector => selector.split(',').some(item => item.trim().startsWith('button')) ? {} : null };
  const stage = { closest: () => null };
  assert.equal(presentationMove({ key: ' ', target: stage }), 1);
  assert.equal(presentationMove({ key: ' ', target: control }), 0);
  assert.equal(presentationMove({ key: 'ArrowRight', target: control }), 1);
  assert.equal(presentationMove({ key: 'ArrowLeft', target: control }), -1);
  assert.equal(presentationMove({ key: 'Escape', target: stage }), 0);
});

test('dialog tab loop recaptures background focus without trapping ordinary traversal', () => {
  const { controls, dialog, focused } = dialogHarness(['exit', 'previous', 'next']);
  const [, previous] = controls;
  const background = {};

  const forward = tab();
  trapDialogTab(dialog, forward, background);
  assert.equal(forward.prevented, true);
  assert.deepEqual(focused, ['exit']);

  focused.length = 0;
  const backward = tab(true);
  trapDialogTab(dialog, backward, background);
  assert.equal(backward.prevented, true);
  assert.deepEqual(focused, ['next']);

  focused.length = 0;
  const ordinary = tab();
  trapDialogTab(dialog, ordinary, previous);
  assert.equal(ordinary.prevented, false);
  assert.deepEqual(focused, []);
});
