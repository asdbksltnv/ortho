import { Route, Routes } from 'react-router-dom'
import { DemoBanner } from './components/DemoBanner'
import { Home } from './pages/Home'

export function App() {
  return (
    <>
      <DemoBanner />
      <Routes>
        <Route path="/" element={<Home />} />
      </Routes>
    </>
  )
}
