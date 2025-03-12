import { type Province, type CoordinateData, CoordinateDataSchema } from "./types/map"
import Logger from "./logger";

const logger = new Logger();
enum AvailableMaps {
  STANDARD = "standard"
}

export let coordinateData: CoordinateData
// --- LOAD COORDINATE DATA ---
export function loadCoordinateData() {
  return new Promise((resolve, reject) => {
    fetch('./assets/maps/standard/coords.json')
      .then(response => {
        if (!response.ok) {
          // Try an alternate path if desired
          throw new Error("Something went wrong when fetching the coords.json")
        }
        return response.json()
      })
      .then(data => {
        coordinateData = data;
        logger.log('Coordinate data loaded!')
        resolve(coordinateData);
      })
      .catch(error => {
        console.error(error);
        reject(error);
      });
  });
}


export default class {
  boardState: CoordinateData | null

  constructor(boardName: AvailableMaps) {
    this.boardState = null
    this._loadMapData(boardName)
  }


  _loadMapData = (boardName: AvailableMaps) => {

    fetch(`./assets/maps/${boardName}/coords.json`)
      .then(response => {
        if (!response.ok) {
          throw new Error(`Failed to load coordinates: ${response.status}`);
        }
        this.boardState = CoordinateDataSchema.parse(response.json())
      })
      .catch(error => {
        console.error(error);
        throw error
      });

  }

}
