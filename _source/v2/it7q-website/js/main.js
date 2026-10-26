/* IT7Q Cyber-Tech Services — main.js */

// ── NAV SCROLL STATE ──
const nav = document.getElementById('mainNav');
window.addEventListener('scroll', () => {
  nav.classList.toggle('scrolled', window.scrollY > 60);
});

// ── MOBILE NAV ──
function toggleMobileNav() {
  const m = document.getElementById('navMobile');
  m.classList.toggle('open');
}

// ── SMOOTH SCROLL FOR NAV LINKS ──
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (target) {
      e.preventDefault();
      const offset = 80;
      const top = target.getBoundingClientRect().top + window.scrollY - offset;
      window.scrollTo({ top, behavior: 'smooth' });
    }
  });
});

// ── PRODUCT TABS ──
function showProdTab(tab) {
  document.querySelectorAll('.products-grid').forEach(g => g.classList.add('hidden'));
  document.querySelectorAll('.prod-tab').forEach(t => t.classList.remove('active'));
  document.getElementById(`prod-${tab}`).classList.remove('hidden');
  event.target.classList.add('active');
}

// ── NDA MODAL ──
function openNDA() {
  document.getElementById('ndaModal').classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeNDA() {
  document.getElementById('ndaModal').classList.remove('open');
  document.body.style.overflow = '';
}

function closeNDAOnOverlay(e) {
  if (e.target === document.getElementById('ndaModal')) closeNDA();
}

function submitNDA() {
  const name  = document.getElementById('ndaName').value.trim();
  const email = document.getElementById('ndaEmail').value.trim();
  const check = document.getElementById('ndaCheck').checked;

  if (!name) { alert('Please enter your full name.'); return; }
  if (!email || !email.includes('@')) { alert('Please enter a valid email address.'); return; }
  if (!check) { alert('Please read and accept the NDA before proceeding.'); return; }

  // Log acceptance (in production this would POST to your backend / n8n webhook)
  const acceptance = {
    name,
    email,
    org: document.getElementById('ndaOrg').value.trim(),
    timestamp: new Date().toISOString(),
    userAgent: navigator.userAgent
  };
  console.log('NDA Accepted:', acceptance);

  // Transition to portal
  document.getElementById('ndaStep1').classList.add('hidden');
  document.getElementById('ndaStep2').classList.remove('hidden');
}

function docPlaceholder(e) {
  e.preventDefault();
  alert('Document will be available upon finalisation. Please contact enquiries@it7q.com.au to request direct access.');
}

// ── CONTACT FORM ──
function submitForm(e) {
  e.preventDefault();

  const payload = {
    name:    document.getElementById('fname').value,
    business: document.getElementById('fbiz').value,
    email:   document.getElementById('femail').value,
    type:    document.getElementById('ftype').value,
    message: document.getElementById('fmsg').value,
    timestamp: new Date().toISOString()
  };

  // In production POST to n8n webhook: https://n8n.nubius.com.au/webhook/website-enquiry
  console.log('Enquiry submitted:', payload);

  // Show success
  document.getElementById('contactForm').querySelector('.form-submit').disabled = true;
  document.getElementById('formSuccess').classList.remove('hidden');

  // Reset after 3 seconds
  setTimeout(() => {
    document.getElementById('contactForm').reset();
    document.getElementById('formSuccess').classList.add('hidden');
    document.getElementById('contactForm').querySelector('.form-submit').disabled = false;
  }, 4000);
}

// ── COOKIE BANNER ──
(function() {
  if (!localStorage.getItem('it7q_cookies_accepted')) {
    document.getElementById('cookieBanner').style.display = 'flex';
  }
})();

function acceptCookies() {
  localStorage.setItem('it7q_cookies_accepted', '1');
  document.getElementById('cookieBanner').style.display = 'none';
}

function dismissCookies() {
  document.getElementById('cookieBanner').style.display = 'none';
}

// ── SCROLL ANIMATIONS ──
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.style.opacity = '1';
      entry.target.style.transform = 'translateY(0)';
    }
  });
}, { threshold: 0.1 });

document.querySelectorAll('.division-card, .product-card, .auto-card, .portfolio-card').forEach(el => {
  el.style.opacity = '0';
  el.style.transform = 'translateY(20px)';
  el.style.transition = 'opacity .5s ease, transform .5s ease';
  observer.observe(el);
});

// ── ESC KEY CLOSES MODAL ──
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') closeNDA();
});
