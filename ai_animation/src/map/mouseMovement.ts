export const addMapMouseEvents = (mapView: HTMLElement, display: HTMLElement) => {
  const isDebugMode = process.env.NODE_ENV === 'development' || localStorage.getItem('debug') === 'true';

  if (isDebugMode) {
    mapView.addEventListener("mousemove", (event) => {
      const rect = mapView.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;

      display.textContent = `X: ${x.toFixed(2)}, Y: ${y.toFixed(2)}\nrect ${JSON.stringify(rect)}`;
    })

  }
}
