/** One file a prompt changed: lines added/removed (null for binary), git status letter. */
export type FileChange = { path: string; added: number | null; removed: number | null; status: string }

/** One typed prompt and the snapshot taken just before it ran. */
export type Prompt = { n: number; text: string; before: string; files: FileChange[]; isDiscarded?: boolean }

/** The last discard, undoable until the next prompt starts. */
export type Undo = { commit: string; n: number }

declare module 'claude-code' {
  interface PluginState {
    'prompt-changes': {
      prompts: Prompt[]
      busy: boolean
      open: number | null
      confirm: number | null
      undo: Undo | null
    }
  }
}
