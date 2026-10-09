// Reading a phase is a user choice, not a business completion state.
export function stylePhases(nodes) {
  let chosen = false;
  const select = () => { chosen = true; };
  const summaries = nodes.map(node => node.querySelector(':scope > summary'));
  summaries.forEach(summary => summary.addEventListener('click', select));
  return {
    show(next, {auto = false} = {}) {
      if (auto && chosen) return;
      nodes.forEach((node, index) => { node.open = index + 1 === next; });
    },
    dispose() { summaries.forEach(summary => summary.removeEventListener('click', select)); }
  };
}
