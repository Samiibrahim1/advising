import type { PropsWithChildren } from 'react'

interface TooltipProps {
  text: string
  /** Inline vs block placement — defaults to inline (question mark icon) */
  inline?: boolean
}

/** 
 * Usage:
 *   <Tooltip text="Explains what this thing does" />
 *   — renders a small ⓘ icon that shows a floating tooltip on hover.
 *
 *   <Tooltip text="Help text"><button>...</button></Tooltip>
 *   — wraps children so that hovering them reveals the tooltip.
 */
export function Tooltip({ text, children }: PropsWithChildren<TooltipProps>) {
  return (
    <span className="tooltip-wrapper">
      {children ?? (
        <span className="tooltip-trigger" aria-label={text}>?</span>
      )}
      <span className="tooltip-bubble" role="tooltip">{text}</span>
    </span>
  )
}
