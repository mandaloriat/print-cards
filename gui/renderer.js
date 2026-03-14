'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------

/** Images selected by the user: key = "ROW,COL", value = absolute file path. */
const selectedImages = {};

/** Current layout config set when clicking "Set Layout". */
let layout = null;

// ---------------------------------------------------------------------------
// Element references
// ---------------------------------------------------------------------------

const stepLayout  = document.getElementById('step-layout');
const stepImages  = document.getElementById('step-images');
const imageGrid   = document.getElementById('image-grid');
const statusEl    = document.getElementById('status');
const outputInput = document.getElementById('output-path');

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function showStatus(type, msg) {
  statusEl.className = type;   // 'success' | 'error' | 'info'
  statusEl.textContent = msg;
  statusEl.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function hideStatus() {
  statusEl.className = '';
  statusEl.textContent = '';
}

/** Read a numeric input's value, returning '' if blank. */
function numVal(id) {
  const v = document.getElementById(id).value.trim();
  return v === '' ? '' : Number(v);
}

/** Validate layout form; return an error string or null. */
function validateLayoutForm() {
  const rows = numVal('rows');
  const cols = numVal('cols');
  const ew   = numVal('element-width');
  const eh   = numVal('element-height');

  if (!rows || rows < 1) return 'Rows must be a positive integer.';
  if (!cols || cols < 1) return 'Columns must be a positive integer.';
  if (!ew || ew <= 0)    return 'Element width must be a positive number.';
  if (!eh || eh <= 0)    return 'Element height must be a positive number.';
  return null;
}

// ---------------------------------------------------------------------------
// Build image-picker grid
// ---------------------------------------------------------------------------

function buildImageGrid(rows, cols) {
  imageGrid.innerHTML = '';

  for (let r = 1; r <= rows; r++) {
    for (let c = 1; c <= cols; c++) {
      const key = `${r},${c}`;

      const cell = document.createElement('div');
      cell.className = 'img-cell';
      cell.dataset.key = key;

      // Thumbnail / placeholder
      const thumb = document.createElement('img');
      thumb.className = 'thumb';
      thumb.style.display = 'none';
      cell.appendChild(thumb);

      const placeholder = document.createElement('div');
      placeholder.className = 'thumb-placeholder';
      placeholder.textContent = '🖼';
      cell.appendChild(placeholder);

      // Position label
      const lbl = document.createElement('div');
      lbl.className = 'cell-label';
      lbl.textContent = `(${r}, ${c})`;
      cell.appendChild(lbl);

      // Choose button
      const btn = document.createElement('button');
      btn.className = 'btn-choose';
      btn.textContent = selectedImages[key] ? '✔ Change…' : 'Choose…';
      btn.addEventListener('click', async () => {
        const filePath = await window.api.openImage();
        if (!filePath) return;

        selectedImages[key] = filePath;

        // Show thumbnail
        thumb.src = `file://${filePath}`;
        thumb.style.display = 'block';
        placeholder.style.display = 'none';
        btn.textContent = '✔ Change…';
        cell.classList.add('has-image');

        hideStatus();
      });
      cell.appendChild(btn);

      // Restore previously chosen image if any
      if (selectedImages[key]) {
        thumb.src = `file://${selectedImages[key]}`;
        thumb.style.display = 'block';
        placeholder.style.display = 'none';
        btn.textContent = '✔ Change…';
        cell.classList.add('has-image');
      }

      imageGrid.appendChild(cell);
    }
  }
}

// ---------------------------------------------------------------------------
// Step 1 → Step 2: Set Layout
// ---------------------------------------------------------------------------

document.getElementById('btn-set-layout').addEventListener('click', () => {
  hideStatus();

  const err = validateLayoutForm();
  if (err) { showStatus('error', err); return; }

  layout = {
    rows:          numVal('rows'),
    cols:          numVal('cols'),
    elementWidth:  numVal('element-width'),
    elementHeight: numVal('element-height'),
    spacingH:      numVal('spacing-h') || 0,
    spacingV:      numVal('spacing-v') || 0,
    marginTop:     numVal('margin-top'),
    marginBottom:  numVal('margin-bottom'),
    marginLeft:    numVal('margin-left'),
    marginRight:   numVal('margin-right'),
    format:        document.getElementById('format').value,
  };

  buildImageGrid(layout.rows, layout.cols);
  stepLayout.style.display  = 'none';
  stepImages.style.display  = 'block';
});

// ---------------------------------------------------------------------------
// Step 2 → Step 1: Back
// ---------------------------------------------------------------------------

document.getElementById('btn-back').addEventListener('click', () => {
  hideStatus();
  stepImages.style.display = 'none';
  stepLayout.style.display = 'block';
});

// ---------------------------------------------------------------------------
// Browse for output PDF
// ---------------------------------------------------------------------------

document.getElementById('btn-browse-output').addEventListener('click', async () => {
  const filePath = await window.api.savePdf();
  if (filePath) outputInput.value = filePath;
});

// ---------------------------------------------------------------------------
// Generate PDF
// ---------------------------------------------------------------------------

document.getElementById('btn-generate').addEventListener('click', async () => {
  hideStatus();

  if (!layout) return;

  // Check all images are chosen
  const missing = [];
  for (let r = 1; r <= layout.rows; r++) {
    for (let c = 1; c <= layout.cols; c++) {
      const key = `${r},${c}`;
      if (!selectedImages[key]) missing.push(`(${r}, ${c})`);
    }
  }
  if (missing.length) {
    showStatus('error', `Please choose an image for: ${missing.join(', ')}`);
    return;
  }

  const outputPath = outputInput.value.trim();
  if (!outputPath) {
    showStatus('error', 'Please specify an output PDF path.');
    return;
  }

  // Build the config payload
  const config = {
    rows:          layout.rows,
    cols:          layout.cols,
    elementWidth:  layout.elementWidth,
    elementHeight: layout.elementHeight,
    spacingH:      layout.spacingH,
    spacingV:      layout.spacingV,
    marginTop:     layout.marginTop,
    marginBottom:  layout.marginBottom,
    marginLeft:    layout.marginLeft,
    marginRight:   layout.marginRight,
    format:        layout.format,
    outputPath,
    images:        Object.assign({}, selectedImages),
  };

  // Disable the button and show a spinner while generating
  const btnGenerate = document.getElementById('btn-generate');
  btnGenerate.disabled = true;
  btnGenerate.innerHTML = '<span class="spinner"></span> Generating…';
  showStatus('info', 'Generating PDF, please wait…');

  try {
    const result = await window.api.generatePdf(config);
    if (result.success) {
      showStatus('success', `✔ ${result.message}`);
    } else {
      showStatus('error', `✖ ${result.message}`);
    }
  } catch (err) {
    showStatus('error', `Unexpected error: ${err.message}`);
  } finally {
    btnGenerate.disabled = false;
    btnGenerate.textContent = 'Generate PDF';
  }
});
