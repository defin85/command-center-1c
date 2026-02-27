- vercel-react-best-practices: “Сделай perf-аудит фронта по Vercel React Best Practices (bundle/code-splitting, re-render, data fetching), предложи и внеси правки”.
- web-design-guidelines: “Проведи UI/UX/a11y аудит страниц фронта по Web Interface Guidelines и дай список нарушений/правок по file:line + исправь критичное”.

https://kb.1ci.com/1C_Enterprise_Platform/Guides/Administrator_Guides/1C_Enterprise_8.3.27_Administrator_Guide/Appendix_4._Startup_command_lines_of_system_components_and_description_of_additional_utilities/4.7._Running_Designer_in_agent_mode/4.7.6._config_group_commands/?language=en

Да, в текущей схеме это так.

  Сейчас cc1c-deploy делает systemctl restart для cc1c-orchestrator, cc1c-api-gateway и обоих worker-ов, поэтому:

  - активные HTTP/WebSocket-сессии у пользователей могут оборваться;
  - в момент рестарта возможны короткие 5xx/reconnect;
  - фоновые задачи на worker-ах тоже перезапускаются (обычно подхватываются заново из очереди).

  Если нужен деплой без заметного прерывания, надо переходить на zero-downtime схему (graceful reload/blue-green/rolling).