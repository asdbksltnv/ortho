import { fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TrendChart } from './TrendChart'

const points = [
  { day: 1, value: 37.2 },
  { day: 2, value: 36.8 },
  { day: 3, value: null },
  { day: 4, value: 36.6 },
]

describe('TrendChart', () => {
  it('names the series in the title and lists values in an accessible label', () => {
    render(<TrendChart title="Температура, °C" unit="°C" points={points} />)
    expect(screen.getByText('Температура, °C')).toBeInTheDocument()
    const img = screen.getAllByRole('img')[0]
    expect(img.getAttribute('aria-label')).toContain('1 — 37,2')
    expect(img.getAttribute('aria-label')).not.toContain('3 —') // missing values are skipped
  })

  it('draws one marker per measured day and no legend box for a single series', () => {
    const { container } = render(<TrendChart title="T" unit="°C" points={points} />)
    expect(container.querySelectorAll('circle[r="4"]')).toHaveLength(3)
    expect(screen.queryByText(/легенда|legend/i)).not.toBeInTheDocument()
    expect(container.querySelector('path')).toHaveAttribute('stroke-width', '2')
  })

  it('shows a tooltip on hover and focus', () => {
    render(<TrendChart title="T" unit="°C" points={points} />)
    const target =
      screen.getAllByLabelText(/сутки после операции|сутки/i)[0] ?? screen.getAllByRole('img')[0]
    fireEvent.focus(target.tagName === 'circle' ? target : screen.getAllByLabelText(/1: 37,2/)[0])
    expect(screen.getByRole('status')).toHaveTextContent('37,2')
  })

  it('offers a table view with the same values', () => {
    render(<TrendChart title="T" unit="°C" points={points} />)
    fireEvent.click(screen.getByRole('button', { name: 'Таблица' }))
    expect(screen.getByRole('table')).toHaveTextContent('36,8')
    expect(screen.getAllByRole('row')).toHaveLength(4) // header + 3 measured days
  })

  it('shows an empty state without data', () => {
    render(<TrendChart title="T" unit="°C" points={[{ day: 1, value: null }]} />)
    expect(screen.getByText('Данных пока нет')).toBeInTheDocument()
  })

  it('handles a single point and integer series', () => {
    render(<TrendChart title="Боль" unit="ВАШ" integer points={[{ day: 2, value: 4 }]} />)
    expect(screen.getAllByRole('img')[0].getAttribute('aria-label')).toContain('2 — 4')
  })
})
