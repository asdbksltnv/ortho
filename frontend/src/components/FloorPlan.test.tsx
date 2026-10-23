import { fireEvent, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { describe, expect, it } from 'vitest'
import type { BoardRow, Ward } from '../api/types'
import { FloorPlan } from './FloorPlan'

const ward: Ward = {
  id: 'w',
  name: 'Отделение, 10 этаж',
  rooms: [
    {
      id: 'r1',
      name: 'Пал. 1001',
      floor: 10,
      position_x: 0,
      position_y: 0,
      width: 60,
      height: 70,
      kind: 'patient',
      beds: [{ id: 'b1', label: 'к. 1', is_active: true }],
    },
    {
      id: 'r2',
      name: 'Пал. 1002',
      floor: 10,
      position_x: 70,
      position_y: 0,
      width: 60,
      height: 70,
      kind: 'patient',
      beds: [{ id: 'b2', label: 'к. 1', is_active: true }],
    },
    {
      id: 'r3',
      name: 'Лифт',
      floor: 10,
      position_x: 140,
      position_y: 0,
      width: 40,
      height: 40,
      kind: 'service',
      beds: [],
    },
    {
      id: 'r4',
      name: 'Выход (лестница)',
      floor: 10,
      position_x: 190,
      position_y: 0,
      width: 40,
      height: 40,
      kind: 'exit',
      beds: [],
    },
  ],
}
const row = {
  case_id: 'c1',
  bed_id: 'b1',
  initials: 'И. А. Д.',
  ready: false,
  blocking: ['docs', 'labs_core'],
  is_emergency: false,
} as BoardRow

function mount() {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<FloorPlan wards={[ward]} rows={[row]} />} />
        <Route path="/case/:id" element={<p>case page</p>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('FloorPlan', () => {
  it('draws occupied, free and service rooms with text, not colour alone', () => {
    mount()
    expect(
      screen.getByRole('link', { name: 'Пал. 1001: И. А. Д.: Не готов (2)' }),
    ).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Пал. 1002: свободно' })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: 'Лифт' })).toBeInTheDocument()
    expect(screen.getByText('▲ Выход')).toBeInTheDocument()
    expect(screen.getByText('✖ И. А. Д.')).toBeInTheDocument()
    expect(screen.getByText('1001')).toBeInTheDocument()
  })

  it('opens the case from the room, by click or keyboard', () => {
    mount()
    fireEvent.keyDown(screen.getByRole('link', { name: /Пал. 1001/ }), { key: 'Enter' })
    expect(screen.getByText('case page')).toBeInTheDocument()
  })

  it('says so when no layout exists', () => {
    render(
      <MemoryRouter>
        <FloorPlan wards={[{ id: 'w', name: 'x', rooms: [] }]} rows={[]} />
      </MemoryRouter>,
    )
    expect(screen.getByText('Расположение палат ещё не задано')).toBeInTheDocument()
  })
})
