import {el, button} from './dom.js';

export const studioStyle = () => document.documentElement.dataset.workbenchUi === 'studio';
let sequence = 0;

// The legacy entry keeps its native disclosure behavior. Studio has one visible
// task stage and explicit navigation; switching stages does not complete work.
export function stylePhase(title, ...body) {
  return studioStyle()
    ? el('section', {class:'style-phase'}, el('h2', {class:'style-phase-heading', tabindex:-1}, title), ...body)
    : el('details', {class:'style-phase'}, el('summary', {}, title), ...body);
}

export function styleDisclosure(title, ...body) {
  if (!studioStyle()) return el('details', {}, el('summary', {}, title), el('div', {class:'stack'}, body));
  const id = `style-tool-${++sequence}`, panel = el('div', {id, class:'style-tool-body stack', hidden:true}, body);
  const trigger = button(title, () => {
    panel.hidden = !panel.hidden; trigger.setAttribute('aria-expanded', String(!panel.hidden));
  }, false, {'aria-expanded':'false', 'aria-controls':id});
  return el('div', {class:'style-tool stack'}, trigger, panel);
}

export function stylePhases(nodes) {
  let chosen = false, active = 1, visible = true;
  const studio = studioStyle();
  const headings = nodes.map(node => node.querySelector(':scope > summary, :scope > .style-phase-heading'));
  const nav = studio ? el('nav', {class:'studio-style-stages', 'aria-label':'风格工作阶段'}) : null;
  const buttons = studio ? headings.map((heading, index) => {
    const title = heading.querySelector('.style-phase-title')?.textContent || heading.textContent;
    const id = `style-stage-${++sequence}`; nodes[index].id = id;
    const action = button(title, () => { chosen = true; show(index + 1); headings[index].focus(); }, false,
      {'aria-controls':id, 'aria-pressed':String(index === 0)});
    nav.append(action); return action;
  }) : [];
  const select = () => { chosen = true; };
  if (!studio) headings.forEach(heading => heading.addEventListener('click', select));
  function show(next, {auto = false} = {}) {
    if (auto && chosen) return;
    active = next;
    nodes.forEach((node, index) => {
      if (studio) { node.hidden = !visible || index + 1 !== active; buttons[index].setAttribute('aria-pressed', String(index + 1 === active)); }
      else node.open = index + 1 === active;
    });
  }
  return {
    nav, show,
    setVisible(value) {
      visible = value; if (nav) nav.hidden = !value;
      if (studio) show(active); else nodes.forEach(node => { node.hidden = !value; });
    },
    dispose() { if (!studio) headings.forEach(heading => heading.removeEventListener('click', select)); }
  };
}
