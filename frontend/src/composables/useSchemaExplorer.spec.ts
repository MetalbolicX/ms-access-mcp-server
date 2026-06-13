// Tests for the useSchemaExplorer composable.
// Strict TDD: RED first. The composable does not exist yet — these tests
// describe the shared-selection-state contract from the unified-schema-explorer
// design (see sdd/unified-schema-explorer/design in Engram).
//
// Contract: useSchemaExplorer() returns a shared ref (selectedTable) and a
// setter (select). The ref is module-scoped so every consumer in the same
// process (e.g. SchemaListPanel + ErDiagramView) sees the same value.
import { describe, it, expect, beforeEach } from 'vitest'
import { nextTick } from 'vue'

describe('useSchemaExplorer composable', () => {
  beforeEach(async () => {
    // Reset the shared ref between tests so leakage from one case does not
    // make the next one trivially pass. We do this by importing the
    // composable, selecting null, and waiting for the reactive flush.
    const { useSchemaExplorer } = await import('./useSchemaExplorer')
    useSchemaExplorer().select(null)
    await nextTick()
  })

  it('exports a select() function and a selectedTable ref', async () => {
    const explorer = await import('./useSchemaExplorer')
    expect(typeof explorer.useSchemaExplorer).toBe('function')
    const { selectedTable, select } = explorer.useSchemaExplorer()
    expect(selectedTable).toBeDefined()
    expect(typeof select).toBe('function')
  })

  it('selectedTable starts as null on a fresh process', async () => {
    const { useSchemaExplorer } = await import('./useSchemaExplorer')
    const { selectedTable } = useSchemaExplorer()
    expect(selectedTable.value).toBeNull()
  })

  it('select(table) updates selectedTable to the given table name', async () => {
    const { useSchemaExplorer } = await import('./useSchemaExplorer')
    const { selectedTable, select } = useSchemaExplorer()
    select('Orders')
    expect(selectedTable.value).toBe('Orders')
  })

  it('select(null) clears the selection', async () => {
    const { useSchemaExplorer } = await import('./useSchemaExplorer')
    const { selectedTable, select } = useSchemaExplorer()
    select('Customers')
    expect(selectedTable.value).toBe('Customers')
    select(null)
    expect(selectedTable.value).toBeNull()
  })

  it('select("") is treated as a clear (no current table is selected)', async () => {
    // Empty string is a sentinel used by the panel for the "no selection"
    // state in its <select> fallback. The composable should still treat it
    // as a valid clear; consumers normalize as needed.
    const { useSchemaExplorer } = await import('./useSchemaExplorer')
    const { selectedTable, select } = useSchemaExplorer()
    select('Products')
    select('')
    expect(selectedTable.value).toBe('')
  })

  it('two consumers of useSchemaExplorer() share the same selectedTable', async () => {
    // This is the central design decision: a module-scoped ref makes the
    // SchemaListPanel and ErDiagramView talk to the same selection state
    // without prop drilling or a Pinia store.
    const { useSchemaExplorer } = await import('./useSchemaExplorer')
    const a = useSchemaExplorer()
    const b = useSchemaExplorer()
    a.select('SharedTable')
    expect(b.selectedTable.value).toBe('SharedTable')
  })

  it('changing selectedTable from one consumer is reactive in the other', async () => {
    // The ref MUST be a Vue ref (not a plain value) so .value assignment
    // triggers reactivity across consumers.
    const { useSchemaExplorer } = await import('./useSchemaExplorer')
    const a = useSchemaExplorer()
    const b = useSchemaExplorer()
    a.select('First')
    await nextTick()
    expect(b.selectedTable.value).toBe('First')
    b.select('Second')
    await nextTick()
    expect(a.selectedTable.value).toBe('Second')
  })
})
