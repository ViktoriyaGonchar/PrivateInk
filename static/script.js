// Theme toggle with localStorage persistence
(function () {
  const root = document.documentElement;
  const THEME_KEY = 'pi_theme';
  function apply(theme) {
    root.setAttribute('data-theme', theme);
    localStorage.setItem(THEME_KEY, theme);
  }
  const saved = localStorage.getItem(THEME_KEY);
  if (saved === 'dark' || saved === 'light') {
    apply(saved);
  } else {
    // Prefer system theme
    const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
    apply(prefersDark ? 'dark' : 'light');
  }
  const toggle = document.getElementById('themeToggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      const next = root.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      apply(next);
    });
  }
})();

// Simple client-side validation enhancer
(function () {
  function attach(formId, fields) {
    const form = document.getElementById(formId);
    if (!form) return;
    form.addEventListener('submit', (e) => {
      let ok = true;
      fields.forEach((f) => {
        const el = form.querySelector(`[name="${f.name}"]`);
        if (!el) return;
        const val = (el.value || '').trim();
        if (f.min && val.length < f.min) ok = false;
        if (f.type === 'email' && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) ok = false;
        if (!val) ok = false;
        if (!ok) {
          el.focus();
        }
      });
      if (!ok) {
        e.preventDefault();
        alert('Проверьте правильность заполнения формы.');
      }
    });
  }
  attach('registerForm', [
    { name: 'username', min: 3 },
    { name: 'email', type: 'email' },
    { name: 'password', min: 6 },
  ]);
  attach('loginForm', [
    { name: 'username', min: 3 },
    { name: 'password', min: 6 },
  ]);
  attach('createForm', [
    { name: 'title', min: 1 },
    { name: 'content', min: 1 },
  ]);
  attach('editForm', [
    { name: 'title', min: 1 },
    { name: 'content', min: 1 },
  ]);
})();



