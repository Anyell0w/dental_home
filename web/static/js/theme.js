/* Tema antes del primer pintado (evita parpadeo). */
try {
  var t = localStorage.getItem('dh-theme');
  if (!t) t = matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  document.documentElement.dataset.theme = t;
} catch (e) {}
