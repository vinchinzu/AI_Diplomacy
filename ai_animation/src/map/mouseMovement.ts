export function addMapMouseEvents(mapView: HTMLElement) {
  const isDebugMode = process.env.NODE_ENV === 'development' || localStorage.getItem('debug') === 'true';

  if (isDebugMode) {
    mapView.addEventListener("mousemove", (event) => {
      const rect = mapView.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;

      // Remove: infoPanel.textContent = `Mouse: (${event.offsetX}, ${event.offsetY})`;
    })
  }
}
