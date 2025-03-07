
enum ProvTypeEnum {
  WATER = "Water",
  COAST = "Coast",
  LAND = "Land",

}
type Province = {
  label: {
    x: number
    y: number
  }
  type: ProvTypeEnum
  unit?: {
    x: number
    y: number
  }
}

type CoordinateData = {
  provinces: Province[]
}
