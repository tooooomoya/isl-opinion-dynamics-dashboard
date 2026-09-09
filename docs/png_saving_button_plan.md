# Implementation Plan - PNG Saving Button for Every Chart

This plan outlines the design and proposed changes to add a "Save as PNG" button to every chart, distribution plot, outcome plane, and network snapshot in the live dashboard.

## Goal Description
The user wants a button to save any rendered chart/visual representation (both SVG-based charts and Canvas-based graphics) as a PNG image directly from the dashboard UI.

## User Review Required
No breaking changes are proposed. The buttons will only appear when hovering over cards (similar to the edit, enlarge, and drag handle icons) to preserve the clean, noise-free layout of the dashboard.

## Proposed Changes

### CSS Styles
We will define styles for `.savebtn` (for metrics cards) and `.card-save-btn` (for generic card panels). These buttons will be styled consistently with existing interactive elements (`.enlargebtn`, `.infobtn`, and `.draghandle`), inheriting theme-compatible hover transitions.

### JavaScript Helper
We will add a utility function `exportToPNG(element, filename)` that handles:
- **Canvas Elements:** Direct export via `canvas.toDataURL("image/png")`.
- **SVG Elements:** XML serialization, Blob conversion, drawing to a temporary canvas (using a 2x scale factor for high-resolution retina exports), filling a solid background matching the current theme (light or dark), and triggering a client-side download.

### Interactive Controls Injection
We will inject the save buttons into the lifecycle of three different types of cards:
1. **Metric Cards (`makeMetricCard`):** Appending a `.savebtn` next to the `.infobtn`.
2. **Dynamic Cards (`makeCard`):** Appending a `.card-save-btn` next to the `.draghandle` for network structure and behavior charts.
3. **Static Cards (`initStaticCard`):** Appending a `.card-save-btn` to the header of the `opinion` distribution, `plane` outcome plane, and `netsnapshot` network views. If no drag handle is present (e.g. for `netsnapshot`), the button will align nicely to the top-right corner.

---

### [MODIFY] dashboard/dashboard.html

#### 1. Add CSS Styles
```css
  /* Save buttons for metric cards and panel cards */
  .savebtn { position:absolute; top:6px; right:56px; cursor:pointer; color:var(--muted);
    font-size:14px; user-select:none; padding:1px 5px; border-radius:4px; line-height:1.4;
    z-index:1; background:none; border:none; opacity:.38; transition:opacity .12s ease, background .12s ease, color .12s ease; }
  .metriccard:hover .savebtn, .metriccard:focus-within .savebtn,
  .savebtn:hover, .savebtn:focus-visible { opacity:1; background:var(--panel-soft); color:var(--ink); }

  .card-save-btn { position:absolute; top:4px; right:28px; cursor:pointer; color:var(--muted);
    font-size:12px; user-select:none; padding:1px 5px; border-radius:4px; line-height:1.4;
    z-index:2; background:none; border:none; opacity:0; transition:opacity .12s ease, background .12s ease, color .12s ease; }
  .panel.card:hover .card-save-btn, .panel.card:focus-within .card-save-btn,
  .card-save-btn:hover, .card-save-btn:focus-visible { opacity:1; background:var(--panel-soft); color:var(--ink); }
```

#### 2. Implement JavaScript Export Helper
```javascript
function exportToPNG(element, filename) {
  if (element instanceof HTMLCanvasElement) {
    const dataURL = element.toDataURL("image/png");
    const link = document.createElement("a");
    link.download = filename;
    link.href = dataURL;
    link.click();
  } else if (element instanceof SVGSVGElement || element.tagName === "svg" || element.querySelector("svg")) {
    const svg = element instanceof SVGSVGElement ? element : element.querySelector("svg");
    if (!svg) return;
    const width = svg.viewBox?.baseVal?.width || svg.clientWidth || 300;
    const height = svg.viewBox?.baseVal?.height || svg.clientHeight || 200;
    const serializer = new XMLSerializer();
    let svgString = serializer.serializeToString(svg);
    if (!svgString.match(/^<svg[^>]+xmlns="http:\/\/www\.w3\.org\/2000\/svg"/)) {
      svgString = svgString.replace(/^<svg/, '<svg xmlns="http://www.w3.org/2000/svg"');
    }
    const img = new Image();
    const svgBlob = new Blob([svgString], {type: "image/svg+xml;charset=utf-8"});
    const url = URL.createObjectURL(svgBlob);
    img.onload = function() {
      const canvas = document.createElement("canvas");
      canvas.width = width * 2;
      canvas.height = height * 2;
      const ctx = canvas.getContext("2d");
      ctx.fillStyle = theme() === "dark" ? "#12161f" : "#ffffff";
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.scale(2, 2);
      ctx.drawImage(img, 0, 0);
      const dataURL = canvas.toDataURL("image/png");
      const link = document.createElement("a");
      link.download = filename;
      link.href = dataURL;
      link.click();
      URL.revokeObjectURL(url);
    };
    img.src = url;
  }
}
```

#### 3. Update Card Construction Functions
* **`makeMetricCard`:** Insert Save button.
* **`makeCard`:** Insert Save button next to the drag handle.
* **`initStaticCard`:** Insert Save button next to the drag handle (or aligned to the edge if no handle exists).

---

## Verification Plan

### Manual Verification
1. Open the dashboard.
2. Hover over any time series card (e.g. `apparentPolarization` or `disagreement`). Click the `⤓` icon and verify a high-resolution PNG is downloaded.
3. Switch to the **Opinion/Outcome** tab. Hover over the **Opinion Distribution** or **Outcome Plane** cards. Click `⤓` and verify the download.
4. Switch to the **Network** tab. Hover over the **Network Snapshot** canvas, click `⤓` and verify that the current canvas frame is downloaded as PNG.
5. Verify that dynamic network structure charts (e.g., Degree CCDF fits, Clustering distribution) can be saved via the save buttons on hover.
