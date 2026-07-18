export function startPoll(fn, ms) {
  let timer = null;
  let stopped = false;
  const tick = async () => {
    if (stopped || document.hidden) return;
    try { await fn(); } catch { /* poll errors are non-fatal */ }
  };
  tick();
  timer = setInterval(tick, ms);
  return () => { stopped = true; if (timer) clearInterval(timer); };
}
