# heartbeat_tasks.md  Tareas Automaticas de Orunex
Edita este archivo para programar tareas periodicas.
Formato: ## Nombre, luego - interval: minutos, - command: instruccion, - enabled: true/false

## Resumen Diario de Noticias
- interval: 1440
- command: [SEARCH_WEB: noticias tecnologia e inteligencia artificial hoy]
- enabled: false

## Limpieza de Logs
- interval: 10080
- command: [CMD: del orunex_outputs\*.log 2>nul]
- enabled: false
