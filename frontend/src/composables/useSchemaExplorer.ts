// useSchemaExplorer — shared selection state for the unified schema explorer.
//
// Design decision (sdd/unified-schema-explorer/design): use a module-scoped
// ref instead of a Pinia store or prop drilling, because the only shared
// state is the currently selected table name. Every consumer
// (SchemaListPanel.vue, ErDiagramView.vue) gets the same ref instance.
//
// PR2 (this slice): only the panel side of the wiring lands here. PR3 adds
// the @node-click → select(node.id) bridge and the fitView() watcher.
import { ref } from 'vue'

const selectedTable = ref<string | null>(null)

export const useSchemaExplorer = () => {
  const select = (table: string | null) => {
    selectedTable.value = table
  }
  return { selectedTable, select }
}
