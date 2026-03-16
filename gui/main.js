'use strict';

const { app, BrowserWindow, ipcMain, dialog } = require('electron');
const { spawn } = require('child_process');
const path = require('path');

// ---------------------------------------------------------------------------
// Window creation
// ---------------------------------------------------------------------------

function createWindow() {
  const win = new BrowserWindow({
    width: 860,
    height: 720,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });
  win.loadFile('index.html');
}

app.whenReady().then(() => {
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});

// ---------------------------------------------------------------------------
// IPC: file dialogs
// ---------------------------------------------------------------------------

/** Open an image file chooser and return the selected path (or null). */
ipcMain.handle('dialog:open-image', async () => {
  const { canceled, filePaths } = await dialog.showOpenDialog({
    title: 'Select image',
    filters: [
      {
        name: 'Images',
        extensions: ['png', 'jpg', 'jpeg', 'gif', 'bmp', 'tiff', 'webp'],
      },
    ],
    properties: ['openFile'],
  });
  return canceled ? null : filePaths[0];
});

/** Open a save dialog for the output PDF and return the path (or null). */
ipcMain.handle('dialog:save-pdf', async () => {
  const { canceled, filePath } = await dialog.showSaveDialog({
    title: 'Save PDF',
    defaultPath: 'output.pdf',
    filters: [{ name: 'PDF', extensions: ['pdf'] }],
  });
  return canceled ? null : filePath;
});

// ---------------------------------------------------------------------------
// IPC: PDF generation
// ---------------------------------------------------------------------------

/**
 * Run `python3 -m print_cards.cli` (falling back to `python`) with all
 * supplied parameters.  Returns { success: boolean, message: string }.
 *
 * config shape:
 *   rows, cols, elementWidth, elementHeight,
 *   spacingH, spacingV,
 *   imageFit,
 *   marginTop, marginBottom, marginLeft, marginRight,  ('' = auto)
 *   offsetX, offsetY,
 *   format, outputPath,
 *   images: { "ROW,COL": "/path/to/image.png", … }
 */
ipcMain.handle('generate-pdf', async (_event, config) => {
  return new Promise((resolve) => {
    const args = [
      '-m', 'print_cards.cli',
      '--rows',           String(config.rows),
      '--cols',           String(config.cols),
      '--element-width',  String(config.elementWidth),
      '--element-height', String(config.elementHeight),
      '--image-fit',      String(config.imageFit),
      '--spacing-h',      String(config.spacingH),
      '--spacing-v',      String(config.spacingV),
      '--format',         String(config.format),
      '--offset-x',       String(config.offsetX),
      '--offset-y',       String(config.offsetY),
      '--output',         String(config.outputPath),
    ];

    if (config.marginTop    !== '')
      args.push('--margin-top',    String(config.marginTop));
    if (config.marginBottom !== '')
      args.push('--margin-bottom', String(config.marginBottom));
    if (config.marginLeft   !== '')
      args.push('--margin-left',   String(config.marginLeft));
    if (config.marginRight  !== '')
      args.push('--margin-right',  String(config.marginRight));

    for (const [key, imgPath] of Object.entries(config.images)) {
      args.push('--image', `${key},${imgPath}`);
    }

    // Try python3 first; fall back to python on Windows / some environments.
    const pythonCmd = process.platform === 'win32' ? 'python' : 'python3';

    let stdout = '';
    let stderr = '';

    const proc = spawn(pythonCmd, args, { stdio: ['ignore', 'pipe', 'pipe'] });

    proc.stdout.on('data', (d) => { stdout += d.toString(); });
    proc.stderr.on('data', (d) => { stderr += d.toString(); });

    proc.on('close', (code) => {
      if (code === 0) {
        resolve({ success: true, message: stdout.trim() || 'PDF generated.' });
      } else {
        resolve({
          success: false,
          message: (stderr.trim() || stdout.trim() || `Process exited with code ${code}`),
        });
      }
    });

    proc.on('error', (err) => {
      resolve({
        success: false,
        message: `Could not start Python: ${err.message}\n\nMake sure Python (with print-cards installed) is on your PATH.`,
      });
    });
  });
});
