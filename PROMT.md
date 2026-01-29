- vercel-react-best-practices: “Сделай perf-аудит фронта по Vercel React Best Practices (bundle/code-splitting, re-render, data fetching), предложи и внеси правки”.
- web-design-guidelines: “Проведи UI/UX/a11y аудит страниц фронта по Web Interface Guidelines и дай список нарушений/правок по file:line + исправь критичное”.

Порядок реализации (чтобы минимизировать пересечения и учесть зависимости):

      1. update-orchestrator-enqueue-consistency (база для корректных ошибок enqueue)
      1.1. update-api-enqueue-503-errors  
      2. update-worker-stream-routing (зависит от стабильного enqueue; пересечение по orchestrator/apps/operations/services/operations_service/workflow.py)
      3. update-orchestrator-eventsubscriber-reliability (после разделения потоков проще сразу учесть полный набор stream’ов/групп)
      4. update-frontend-performance (сначала “поведенческие”/архитектурные правки подписок и imports)
      5. update-frontend-ui-ux-a11y (после performance, т.к. есть пересечение по frontend/src/stores/serviceMeshManager.ts)
      6. add-tenancy-extensions-plan-apply (самый широкий change; лучше после стабилизации фронта/оркестратора, чтобы уменьшить количество конфликтов)