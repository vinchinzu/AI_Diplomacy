import { type Province, type CoordinateData, CoordinateDataSchema } from "./types/map"

enum AvailableMaps {
  STANDARD = "standard"
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
