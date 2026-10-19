// Edition flag. The GitHub Pages build sets window.AHDAF_STATIC = true: the backend then runs in the
// browser (Pyodide) instead of on a server, routes use the URL hash, and PDFs are printed locally.
export const STATIC = typeof window !== 'undefined' && window.AHDAF_STATIC === true;
