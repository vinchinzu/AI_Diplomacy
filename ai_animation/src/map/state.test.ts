import { describe, it, expect, beforeEach, vi } from 'vitest'
import { PowerENUM, ProvinceENUM, ProvTypeENUM } from '../types/map'
import { MeshBasicMaterial } from 'three'
import { updateMapOwnership } from './state'
import { gameState } from '../gameState'

// Mock the gameState import
vi.mock('../gameState', () => ({
  gameState: {
    gameData: {
      phases: [
        {
          state: {
            influence: {
              FRANCE: ['PAR', 'BRE'],
              GERMANY: ['BER', 'KIE'],
              ENGLAND: ['LON', 'LVP']
            }
          }
        }
      ]
    },
    phaseIndex: 0,
    boardState: {
      provinces: {
        PAR: {
          type: ProvTypeENUM.LAND,
          owner: undefined,
          mesh: {
            material: new MeshBasicMaterial()
          }
        },
        BRE: {
          type: ProvTypeENUM.COAST,
          owner: undefined,
          mesh: {
            material: new MeshBasicMaterial()
          }
        },
        BER: {
          type: ProvTypeENUM.LAND,
          owner: undefined,
          mesh: {
            material: new MeshBasicMaterial()
          }
        },
        KIE: {
          type: ProvTypeENUM.COAST,
          owner: undefined,
          mesh: {
            material: new MeshBasicMaterial()
          }
        },
        LON: {
          type: ProvTypeENUM.COAST,
          owner: undefined,
          mesh: {
            material: new MeshBasicMaterial()
          }
        },
        LVP: {
          type: ProvTypeENUM.COAST,
          owner: undefined,
          mesh: {
            material: new MeshBasicMaterial()
          }
        },
        NAT: {
          type: ProvTypeENUM.WATER,
          owner: undefined,
          mesh: {
            material: new MeshBasicMaterial()
          }
        }
      }
    }
  }
}))

describe('updateMapOwnership', () => {
  beforeEach(() => {
    // Reset all provinces to have no owner before each test
    Object.values(gameState.boardState.provinces).forEach(province => {
      province.owner = undefined
    })
    // Reset phase index
    gameState.phaseIndex = 0
    // Reset influence data to default
    gameState.gameData.phases[0].state.influence = {
      FRANCE: [ProvinceENUM.PAR, ProvinceENUM.BRE],
      GERMANY: [ProvinceENUM.BER, ProvinceENUM.KIE],
      ENGLAND: [ProvinceENUM.LON, ProvinceENUM.LVP]
    }
  })

  it('should update province ownership based on influence data', () => {
    updateMapOwnership()

    // Check that French provinces are owned by France
    expect(gameState.boardState.provinces.PAR.owner).toBe(PowerENUM.FRANCE)
    expect(gameState.boardState.provinces.BRE.owner).toBe(PowerENUM.FRANCE)

    // Check that German provinces are owned by Germany
    expect(gameState.boardState.provinces.BER.owner).toBe(PowerENUM.GERMANY)
    expect(gameState.boardState.provinces.KIE.owner).toBe(PowerENUM.GERMANY)

    // Check that English provinces are owned by England
    expect(gameState.boardState.provinces.LON.owner).toBe(PowerENUM.ENGLAND)
    expect(gameState.boardState.provinces.LVP.owner).toBe(PowerENUM.ENGLAND)

    // Check that water provinces remain unowned
    expect(gameState.boardState.provinces.NAT.owner).toBeUndefined()
  })

  it('should clear existing ownership before setting new ownership', () => {
    // Set initial ownership
    gameState.boardState.provinces.PAR.owner = PowerENUM.ENGLAND
    gameState.boardState.provinces.BER.owner = PowerENUM.AUSTRIA

    updateMapOwnership()

    // Verify ownership is correctly updated to match influence data
    expect(gameState.boardState.provinces.PAR.owner).toBe(PowerENUM.FRANCE)
    expect(gameState.boardState.provinces.BER.owner).toBe(PowerENUM.GERMANY)
  })

  it('should throw error when phase index is invalid', () => {
    gameState.phaseIndex = 9999999

    expect(() => updateMapOwnership()).toThrow('Current phase is undefined for index 999')
  })

  it('should handle empty influence data', () => {
    gameState.gameData.phases[0].state.influence = {}

    updateMapOwnership()

    // All provinces should have no owner
    Object.values(gameState.boardState.provinces).forEach(province => {
      expect(province.owner).toBeUndefined()
    })
  })
})
