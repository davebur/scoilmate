// Show/hide button for password fields. External file only: the CSP allows 'self' scripts and no inline code.
(function () {
  'use strict';
  document.querySelectorAll('[data-password-toggle]').forEach(function (button) {
    var input = document.getElementById(button.getAttribute('aria-controls'));
    if (!input) return;
    button.addEventListener('click', function () {
      var show = input.type === 'password';
      input.type = show ? 'text' : 'password';
      button.setAttribute('aria-pressed', String(show));
      button.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
      button.textContent = show ? '🙈' : '👁';
    });
  });
})();
