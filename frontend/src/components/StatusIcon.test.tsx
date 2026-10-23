import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import type { ItemStatus } from '../api/types'
import { StatusIcon } from './StatusIcon'

const LABELS: Record<ItemStatus, string> = {
  not_started: 'Не начато',
  pending: 'В процессе',
  done: 'Выполнено',
  problem: 'Проблема',
  not_applicable: 'Не требуется',
}

describe('StatusIcon', () => {
  it.each(Object.entries(LABELS))('%s has a text label', (status, label) => {
    render(<StatusIcon status={status as ItemStatus} />)
    expect(screen.getByRole('img', { name: label })).toBeInTheDocument()
  })

  it('draws a different shape per status (not colour alone)', () => {
    const shapes = (Object.keys(LABELS) as ItemStatus[]).map((s) => {
      const { container, unmount } = render(<StatusIcon status={s} />)
      const markup = [...container.querySelectorAll('svg > *:not(title)')]
        .map((n) => n.tagName + (n.getAttribute('d') ?? n.getAttribute('r') ?? ''))
        .join('|')
      unmount()
      return markup
    })
    expect(new Set(shapes).size).toBe(shapes.length)
  })
})
