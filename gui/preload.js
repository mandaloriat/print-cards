'use strict';

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
  /** Open a native image file chooser; returns the selected path or null. */
  openImage: () => ipcRenderer.invoke('dialog:open-image'),

  /** Open a native save dialog for PDF output; returns the path or null. */
  savePdf: () => ipcRenderer.invoke('dialog:save-pdf'),

  /** Generate the PDF by calling the Python back-end.
   *  @param {object} config - Layout + image configuration (see main.js for shape).
   *  @returns {Promise<{success: boolean, message: string}>}
   */
  generatePdf: (config) => ipcRenderer.invoke('generate-pdf', config),
});
