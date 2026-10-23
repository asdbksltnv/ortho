import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import intakeRu from './intake.ru.json'
import ru from './ru.json'
import uz from './uz.json'

void i18n.use(initReactI18next).init({
  resources: {
    ru: { translation: ru, intake: intakeRu },
    uz: { translation: uz },
  },
  lng: 'ru',
  fallbackLng: 'ru',
  interpolation: { escapeValue: false },
})

export default i18n
