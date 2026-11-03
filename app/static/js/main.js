document.addEventListener('DOMContentLoaded', () => {
  fetch('/static/data/india-cities.json')
    .then((response) => response.json())
    .then((locations) => {
      document.querySelectorAll('[data-state-select]').forEach((stateSelect) => {
        const form = stateSelect.closest('form');
        const citySelect = form.querySelector('[data-city-select]');
        const cityManual = form.querySelector('[data-city-manual]');
        const cityRequired = citySelect.required || cityManual.required;
        const cityLabel = citySelect.closest('label');
        cityManual.remove();
        citySelect.name = 'city';

        Object.keys(locations.states).sort().forEach((state) => {
          stateSelect.add(new Option(state, state));
        });
        stateSelect.disabled = false;

        const populateCities = (selectedCity = '') => {
          const cities = locations.states[stateSelect.value] || [];
          citySelect.replaceChildren(new Option('Choose a city', ''));
          cities.forEach((city) => citySelect.add(new Option(city, city)));
          citySelect.disabled = cities.length === 0;
          citySelect.required = cityRequired;
          if (selectedCity && cities.includes(selectedCity)) citySelect.value = selectedCity;
          if (!cities.length) {
            citySelect.add(new Option('No city data available', ''));
            citySelect.disabled = true;
            citySelect.required = false;
          }
          if (cityLabel) cityLabel.dataset.cityCount = String(cities.length);
        };

        stateSelect.addEventListener('change', () => populateCities());
        const query = new URLSearchParams(window.location.search);
        if (query.has('state') && locations.states[query.get('state')]) {
          stateSelect.value = query.get('state');
          populateCities(query.get('city') || '');
        }
      });
    })
    .catch(() => {
      document.querySelectorAll('[data-city-select]').forEach((citySelect) => {
        citySelect.replaceChildren(new Option('City list unavailable', ''));
        citySelect.disabled = true;
      });
    });

  const savedTheme = localStorage.getItem('rakta-theme') || 'dark';
  document.body.dataset.theme = savedTheme;

  const paletteTokens = {
    'red-blue': { dark: ['#d94d59', '#b93649', '#5b91bd'], light: ['#c64250', '#a72d42', '#3976a6'] },
    berry: { dark: ['#c76179', '#9d4967', '#8292bd'], light: ['#a84461', '#8f3554', '#536d9c'] },
    ocean: { dark: ['#e07866', '#c65a52', '#61a6ba'], light: ['#b95045', '#9c3f3c', '#28728d'] },
    forest: { dark: ['#78b889', '#4d9467', '#8bb6a5'], light: ['#32744a', '#245c39', '#377a70'] },
    lavender: { dark: ['#ad94e8', '#8669c5', '#82a2df'], light: ['#7252ad', '#593c91', '#426aab'] },
    sunset: { dark: ['#f0a45f', '#d47748', '#d9818a'], light: ['#b85528', '#91401f', '#a63e5b'] },
    gold: { dark: ['#e5ba60', '#c39135', '#7db2aa'], light: ['#96610d', '#754800', '#33776f'] }
  };
  let siteAppearance = { palette: 'red-blue', motion_level: 'balanced', live_background: true };
  const applyPalette = () => {
    const tokens = (paletteTokens[siteAppearance.palette] || paletteTokens['red-blue'])[document.body.dataset.theme];
    document.body.style.setProperty('--primary', tokens[0]);
    document.body.style.setProperty('--primary-strong', tokens[1]);
    document.body.style.setProperty('--secondary', tokens[2]);
  };
  applyPalette();

  const themeToggle = document.querySelector('.theme-toggle');
  if (themeToggle) {
    const updateToggleLabel = () => {
      const isLight = document.body.dataset.theme === 'light';
      themeToggle.querySelector('.theme-icon').textContent = isLight ? '☾' : '☀';
      themeToggle.setAttribute('aria-pressed', String(isLight));
    };
    updateToggleLabel();
    themeToggle.addEventListener('click', () => {
      const nextTheme = document.body.dataset.theme === 'dark' ? 'light' : 'dark';
      document.body.dataset.theme = nextTheme;
      localStorage.setItem('rakta-theme', nextTheme);
      applyPalette();
      updateToggleLabel();
    });
  }

  document.querySelectorAll('[data-password-toggle]').forEach((toggle) => {
    const input = toggle.closest('.password-field').querySelector('input');
    toggle.addEventListener('click', () => {
      const isVisible = input.type === 'text';
      input.type = isVisible ? 'password' : 'text';
      toggle.setAttribute('aria-label', isVisible ? 'Show password' : 'Hide password');
      toggle.setAttribute('title', isVisible ? 'Show password' : 'Hide password');
      toggle.classList.toggle('is-visible', !isVisible);
    });
  });

  const reveals = document.querySelectorAll('.reveal');
  reveals.forEach((el, index) => {
    setTimeout(() => el.classList.add('visible'), index * 120);
  });

  const logoutButton = document.querySelector('[data-logout]');
  if (logoutButton) {
    logoutButton.addEventListener('click', async () => {
      const csrfToken = document.querySelector('meta[name="csrf-token"]')?.content;
      const response = await fetch('/api/auth/logout', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...(csrfToken ? { 'X-CSRF-Token': csrfToken } : {})
        }
      });
      if (response.ok) {
        window.location.href = '/';
      }
    });
  }

  const bloodGroupCards = document.querySelectorAll('.blood-group-card');
  bloodGroupCards.forEach((card) => {
    card.addEventListener('click', () => {
      bloodGroupCards.forEach((item) => item.classList.remove('active'));
      card.classList.add('active');
    });
  });

  const homeSearchForm = document.getElementById('homeSearchForm');
  if (homeSearchForm) {
    homeSearchForm.addEventListener('submit', (event) => {
      event.preventDefault();
      const formData = new FormData(homeSearchForm);
      const params = new URLSearchParams(formData).toString();
      window.location.href = `/find-blood?${params}`;
    });
  }

  const startGlobalMotion = (settings) => {
    const motionCanvas = document.querySelector('.site-motion');
    if (!motionCanvas || !settings.live_background) {
      if (motionCanvas) motionCanvas.hidden = true;
      return;
    }
    document.body.dataset.motionLevel = settings.motion_level;
    if (settings.motion_level === 'reduced' || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const context = motionCanvas.getContext('2d');
    const points = [];
    let width = 0;
    let height = 0;
    let pointer = { x: -1000, y: -1000 };
    let frame = 0;
    const random = (minimum, maximum) => minimum + Math.random() * (maximum - minimum);

    const resize = () => {
      const bounds = motionCanvas.getBoundingClientRect();
      const scale = Math.min(window.devicePixelRatio || 1, 2);
      width = bounds.width;
      height = bounds.height;
      motionCanvas.width = Math.round(width * scale);
      motionCanvas.height = Math.round(height * scale);
      context.setTransform(scale, 0, 0, scale, 0, 0);
      const density = settings.motion_level === 'expressive' ? 11500 : 23000;
      const maximum = settings.motion_level === 'expressive' ? 90 : 50;
      const count = Math.max(20, Math.min(maximum, Math.round(width * height / density)));
      points.length = 0;
      for (let index = 0; index < count; index += 1) {
        points.push({ x: random(0, width), y: random(0, height), dx: random(-0.18, 0.18), dy: random(-0.16, 0.16), phase: random(0, Math.PI * 2) });
      }
    };

    const draw = () => {
      context.clearRect(0, 0, width, height);
      points.forEach((point, index) => {
        const speed = settings.motion_level === 'expressive' ? 1.8 : 1;
        point.x += point.dx * speed;
        point.y += point.dy * speed;
        if (point.x < -10 || point.x > width + 10) point.dx *= -1;
        if (point.y < -10 || point.y > height + 10) point.dy *= -1;
        const glow = 0.5 + Math.sin(frame * 0.012 + point.phase) * 0.24;
        const distanceFromPointer = Math.hypot(pointer.x - point.x, pointer.y - point.y);
        if (distanceFromPointer < 150) {
          point.x += ((point.x - pointer.x) / Math.max(distanceFromPointer, 1)) * (150 - distanceFromPointer) * 0.008;
        }
        for (let otherIndex = index + 1; otherIndex < points.length; otherIndex += 1) {
          const other = points[otherIndex];
          const distance = Math.hypot(point.x - other.x, point.y - other.y);
          if (distance < 112) {
            context.strokeStyle = distance < 58 ? `rgba(69, 132, 190, ${0.17 * (1 - distance / 112)})` : `rgba(207, 79, 89, ${0.12 * (1 - distance / 112)})`;
            context.lineWidth = 0.7;
            context.beginPath();
            context.moveTo(point.x, point.y);
            context.lineTo(other.x, other.y);
            context.stroke();
          }
        }
        context.fillStyle = index % 3 === 0 ? `rgba(205, 75, 88, ${glow})` : `rgba(78, 145, 202, ${glow})`;
        context.beginPath();
        context.arc(point.x, point.y, index % 6 === 0 ? 2 : 1.15, 0, Math.PI * 2);
        context.fill();
      });
      frame += 1;
      requestAnimationFrame(draw);
    };

    window.addEventListener('pointermove', (event) => {
      const bounds = motionCanvas.getBoundingClientRect();
      const inside = event.clientX >= bounds.left && event.clientX <= bounds.right && event.clientY >= bounds.top && event.clientY <= bounds.bottom;
      pointer = inside ? { x: event.clientX - bounds.left, y: event.clientY - bounds.top } : { x: -1000, y: -1000 };
    });
    window.addEventListener('resize', resize, { passive: true });
    resize();
    draw();
  };

  fetch('/api/site/appearance')
    .then((response) => response.ok ? response.json() : Promise.reject(new Error('Appearance settings unavailable')))
    .then((result) => {
      siteAppearance = result.data;
      applyPalette();
      startGlobalMotion(siteAppearance);
    })
    .catch(() => startGlobalMotion(siteAppearance));
});
