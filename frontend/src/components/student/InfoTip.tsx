import { Info } from 'lucide-react'
import { isValidElement, useId, useRef, useState, type PointerEvent, type ReactElement, type ReactNode } from 'react'

import { Tooltip, TooltipPopup, TooltipTrigger } from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'

interface InfoTipProps {
  /** The explanation shown in the glass tip. */
  content: ReactNode
  /** Accessible name of the default (i) trigger. */
  label?: string
  /** A focusable element (button, link) to describe instead of the default (i) button; it receives the trigger props. */
  children?: ReactElement<{ children?: ReactNode }>
  side?: 'top' | 'bottom' | 'left' | 'right'
  className?: string
}

/**
 * Glass tooltip on the ui/tooltip primitive. Opens on hover and keyboard focus (base-ui), on tap on touch screens
 * and closes with Escape or a second tap. The trigger is a 44px button; the text is also its aria-describedby.
 */
export function InfoTip({ content, label = 'Más información', children, side = 'top', className }: InfoTipProps) {
  const [open, setOpen] = useState(false)
  const pointerType = useRef('')
  const descriptionId = useId()

  const onPointerDown = (event: PointerEvent<HTMLElement>) => {
    pointerType.current = event.pointerType
  }
  // Touch has no hover or focus ring: a tap toggles the tip. Mouse and keyboard keep the base-ui behaviour.
  const onClick = () => {
    if (pointerType.current === 'touch') setOpen((current) => !current)
    pointerType.current = ''
  }

  const custom = isValidElement<{ children?: ReactNode }>(children)

  return (
    <Tooltip open={open} onOpenChange={setOpen}>
      <TooltipTrigger
        render={custom ? children : <button type="button" aria-label={label} className={cn('sp-infotip-trigger', className)} />}
        aria-describedby={descriptionId}
        onPointerDown={onPointerDown}
        onClick={onClick}
      >
        {custom ? children.props.children : <Info aria-hidden="true" />}
      </TooltipTrigger>
      <span id={descriptionId} className="sp-sr-only">
        {content}
      </span>
      <TooltipPopup side={side} sideOffset={8} role="tooltip" className="sp-tip">
        {content}
      </TooltipPopup>
    </Tooltip>
  )
}
