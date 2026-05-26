/**
 * Three-panel horizontal resize (left + center + right).
 * @param {{ left: HTMLElement, center?: HTMLElement, right: HTMLElement, leftHandle?: HTMLElement, rightHandle?: HTMLElement, leftMin?: number, leftMax?: number, rightMin?: number, rightMax?: number }} config
 */
function initThreePanelResize(config) {
  const left = config.left;
  const right = config.right;
  const leftHandle = config.leftHandle;
  const rightHandle = config.rightHandle;

  if (!left || !right) return;

  const leftMin = config.leftMin ?? 180;
  const leftMax = config.leftMax ?? 400;
  const rightMin = config.rightMin ?? 250;
  const rightMax = config.rightMax ?? 800;

  function bindResize(handle, panel, getStartWidth, computeWidth) {
    if (!handle || !panel) return;

    let isResizing = false;
    let startX = 0;
    let startWidth = 0;

    handle.addEventListener("mousedown", (e) => {
      isResizing = true;
      startX = e.clientX;
      startWidth = getStartWidth();
      handle.classList.add("resizing");
      document.body.style.cursor = "col-resize";
      document.body.style.userSelect = "none";
      e.preventDefault();
    });

    document.addEventListener("mousemove", (e) => {
      if (!isResizing) return;
      const newWidth = computeWidth(startX, e.clientX, startWidth);
      if (newWidth >= panel.min && newWidth <= panel.max) {
        panel.el.style.width = `${newWidth}px`;
      }
    });

    document.addEventListener("mouseup", () => {
      if (!isResizing) return;
      isResizing = false;
      handle.classList.remove("resizing");
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    });
  }

  bindResize(
    leftHandle,
    { el: left, min: leftMin, max: leftMax },
    () => left.offsetWidth,
    (startX, clientX, startWidth) => startWidth + (clientX - startX)
  );

  bindResize(
    rightHandle,
    { el: right, min: rightMin, max: rightMax },
    () => right.offsetWidth,
    (startX, clientX, startWidth) => startWidth + (startX - clientX)
  );
}

if (typeof window !== "undefined") {
  window.initThreePanelResize = initThreePanelResize;
}
