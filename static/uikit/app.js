document.addEventListener('DOMContentLoaded', function () {
  hljs.highlightAll();
});

let alertWrapper = document.querySelector('.alert')
let alertClose = document.querySelector('.alert__close')

if (alertWrapper) {
  alertClose.addEventListener('click', () =>
    alertWrapper.style.display = 'none'
  )
}

// Attendance toggle (AJAX — no full page refresh)
document.querySelectorAll('form.training__attendance').forEach(function (form) {
  form.addEventListener('submit', function (event) {
    event.preventDefault();

    const button = form.querySelector('button.attendance-check');
    if (button.disabled) return;
    button.disabled = true;

    const formData = new FormData(form);

    fetch(form.action, {
      method: 'POST',
      body: formData,
      headers: { 'X-Requested-With': 'XMLHttpRequest' },
      credentials: 'same-origin',
    })
      .then(function (response) {
        if (!response.ok) throw new Error('Request failed');
        return response.json();
      })
      .then(function (data) {
        const status = data.status;
        button.classList.remove(
          'attendance-check--pending',
          'attendance-check--present',
          'attendance-check--absent'
        );
        button.classList.add('attendance-check--' + status);
        button.setAttribute('aria-label', 'Attendance: ' + status);
        button.setAttribute('title', 'Attendance: ' + status.charAt(0).toUpperCase() + status.slice(1));
        if (status === 'present') button.innerHTML = '&#10003;';
        else if (status === 'absent') button.innerHTML = '&#10007;';
        else button.innerHTML = '';
      })
      .catch(function () {
        // Fallback: let the form submit normally so the user still gets the update
        form.submit();
      })
      .finally(function () {
        button.disabled = false;
      });
  });
});
