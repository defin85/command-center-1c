## 1. Accessibility (a11y)
- [ ] Icon-only кнопки: добавить `aria-label` (или заменить на `<Button>` с текстом).
- [ ] Интерактивные элементы: обеспечить клавиатуру (Enter/Space) и фокусируемость; избегать кликабельных `<div>/<span>/<Tag>`.
- [ ] Формы/фильтры: для `Input/Select` без `Form.Item label` добавить `aria-label` (или связанный label).
- [ ] Добавить “skip link” к основному контенту и семантический `<main>` (минимально, без редизайна).

## 2. Typography / Copy
- [ ] Заменить `...` на `…` в UI тексте и статусах (loading/empty state/connecting/reconnecting).
- [ ] Проверить консистентность языка/Title Case на основных страницах (опционально, без переименования доменных терминов).

## 3. Validation
- [ ] `cd frontend && npm run lint`
- [ ] `cd frontend && npm run test:run`
- [ ] (опционально) Playwright smoke для основных страниц после правок

