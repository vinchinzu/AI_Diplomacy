
export default class Logger {
  get infoPanel() {
    let _panel = document.getElementById('info-panel');
    if (_panel === null) {
      throw new Error("Unable to find the element with id 'info-panel'")
    }
    return _panel
  }
  log = (msg: string) => {
    if (typeof msg !== "string") {
      throw new Error(`Logger messages must be strings, you passed a ${typeof msg}`)
    }
    this.infoPanel.textContent = msg;

    console.log(msg)
  }
}
