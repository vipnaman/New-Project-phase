document.addEventListener('DOMContentLoaded', () => {
  const network = document.querySelector('.blood-network');
  if (!network) return;

  const move = (event) => {
    const rect = network.getBoundingClientRect();
    const px = (event.clientX - rect.left) / rect.width - 0.5;
    const py = (event.clientY - rect.top) / rect.height - 0.5;
    network.style.transform = `translate(${px * 8}px, ${py * 8}px)`;
  };

  network.addEventListener('pointermove', move);
  network.addEventListener('pointerleave', () => {
    network.style.transform = 'translate(0, 0)';
  });
});
