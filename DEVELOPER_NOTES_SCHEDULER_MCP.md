# Notas del Desarrollador: MCP de Programación (Scheduler MCP)

Fecha: 2025-05-11

## 1. Resumen General

El MCP (Micro Content Processor) de Programación, también conocido como Scheduler MCP, es un microservicio FastAPI diseñado para gestionar la programación de tareas de publicación de contenido en diversas plataformas. Permite a los usuarios de GENIA programar la publicación de contenido en un momento futuro específico.

Funcionalidades principales:
- Crear nuevas tareas programadas.
- Listar tareas programadas (con filtros opcionales).
- Obtener detalles de una tarea específica.
- Cancelar (eliminar) tareas programadas.
- Utiliza APScheduler para la ejecución de las tareas en el momento programado.

## 2. Decisiones Técnicas Clave

- **Framework**: FastAPI por su rendimiento y facilidad de uso para construir APIs con Python.
- **Servidor ASGI**: Uvicorn con recarga automática para desarrollo (`--reload`).
- **Base de Datos**: SQLAlchemy como ORM, con SQLite (`scheduler.db`) para el almacenamiento de la información de las tareas y `scheduler_jobs.db` para el job store de APScheduler. Se recomienda migrar a PostgreSQL para producción.
- **Programación de Tareas**: APScheduler (`AsyncIOScheduler`) con `SQLAlchemyJobStore` para persistir los trabajos de programación.
- **Validación de Datos**: Pydantic para la validación de modelos de solicitud y respuesta.
- **Conversión ORM a Pydantic**: Se implementó una función de ayuda explícita `convert_task_orm_to_pydantic` en `app/api/api_router.py` para manejar la transformación de los modelos SQLAlchemy (`ScheduledTaskTable`) a los modelos de respuesta Pydantic (`ScheduledTaskResponse`). Esto fue necesario debido a que campos como `platform_identifier` y `task_payload` se construyen a partir de múltiples columnas en la tabla ORM o se almacenan como JSON serializado (`task_payload_json`, `user_platform_tokens_json`, `execution_result_json`). La configuración `from_attributes=True` en los modelos Pydantic no fue suficiente por sí sola para manejar esta complejidad.

## 3. Desafíos Encontrados y Soluciones

1.  **Error de Importación Inicial**: Al intentar ejecutar `python3.11 app/main.py` directamente, se produjo un `ModuleNotFoundError: No module named 'app'`. 
    *   **Solución**: Se corrigió ejecutando el servicio con Uvicorn desde el directorio raíz del proyecto: `python3.11 -m uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload`.

2.  **`NameError: name 'Depends' is not defined`**: En `app/services/scheduler_service.py`.
    *   **Solución**: Se añadió la importación `from fastapi import Depends`.

3.  **Puerto Ocupado (`Address already in use`)**: El puerto 8001 a veces quedaba ocupado por instancias previas del servidor.
    *   **Solución**: Se instaló `lsof` (`sudo apt-get install -y lsof`) y se utilizó `lsof -t -i:8001 | xargs -r kill -9` para liberar el puerto antes de reiniciar el servidor.

4.  **Inestabilidad de URL Pública Temporal**: La URL pública generada por `deploy_expose_port` no siempre era accesible o dejaba de funcionar rápidamente, impidiendo las pruebas externas.
    *   **Solución**: Se optó por realizar pruebas funcionales exhaustivas localmente dentro del entorno del sandbox. Primero se verificó la operatividad del servicio con `curl http://localhost:8001/ping`. Luego, se modificó el script de pruebas (`test_scheduler_mcp.py`) para apuntar a `http://localhost:8001/api/v1`.

5.  **Error 500 en Creación de Tareas (`Internal Server Error`)**: Las pruebas locales iniciales fallaron con un error 500 al intentar crear tareas.
    *   **Diagnóstico**: La revisión de los logs de Uvicorn reveló una `pydantic_core._pydantic_core.ValidationError`. Inicialmente se pensó que `from_attributes=True` en el modelo Pydantic sería suficiente.
    *   **Diagnóstico Avanzado**: Logs más detallados mostraron que el error de validación se debía a que los campos anidados `platform_identifier` y `task_payload` eran requeridos por el modelo `ScheduledTaskResponse` pero no se estaban construyendo correctamente a partir del objeto ORM `ScheduledTaskTable`. El ORM almacena estos datos en columnas separadas (ej. `platform_name`, `account_id`) o como cadenas JSON (`task_payload_json`, `user_platform_tokens_json`).
    *   **Solución Final**: Se implementó la función `convert_task_orm_to_pydantic` en `app/api/api_router.py`. Esta función:
        1.  Deserializa los campos JSON (`task_payload_json`, `user_platform_tokens_json`, `execution_result_json`) del objeto ORM.
        2.  Construye explícitamente los objetos Pydantic anidados (`PlatformIdentifier`, `ScheduledTaskPayload`).
        3.  Crea la instancia final de `ScheduledTaskResponse` con todos los campos correctamente poblados.
        Los endpoints de la API fueron actualizados para usar esta función de conversión antes de devolver las respuestas.

## 4. Pruebas Realizadas

- **Prueba de Ping Local**: `curl -X GET http://localhost:8001/ping` (Exitosa, devolvió `{"ping":"pong!"}`).
- **Script de Pruebas Funcionales Locales (`test_scheduler_mcp.py`)**: Este script cubre:
    - Creación de una nueva tarea (POST /tasks).
    - Listado de tareas para verificar la creación (GET /tasks).
    - Obtención de la tarea específica por ID (GET /tasks/{task_id}).
    - Eliminación de la tarea (DELETE /tasks/{task_id}).
    - Listado de tareas para verificar la eliminación (GET /tasks).
    Todas las pruebas en este script fueron exitosas después de las correcciones en la conversión ORM-Pydantic.

## 5. Consideraciones Futuras y Recomendaciones

- **Exposición Pública para Pruebas**: Investigar más a fondo la inestabilidad de `deploy_expose_port` para servicios FastAPI con Uvicorn o considerar herramientas alternativas (como ngrok instalado manualmente) si se requieren pruebas externas robustas durante el desarrollo.
- **Base de Datos**: Para un entorno de producción, migrar de SQLite a una base de datos más robusta como PostgreSQL. Actualizar `DATABASE_URL` y `SCHEDULER_DATABASE_URL` en `app/core/config.py`.
- **Autenticación**: Implementar un mecanismo de autenticación real y seguro para proteger los endpoints del MCP. El token `MCP_API_TOKEN_SECRET` en `app/core/config.py` debe ser gestionado de forma segura (ej. variables de entorno) y la lógica de verificación de token (actualmente `placeholder_auth_dependency`) debe ser completada.
- **Manejo de Errores en Conversión**: Mejorar el manejo de errores dentro de `convert_task_orm_to_pydantic`, especialmente para fallos en la deserialización de JSON (actualmente imprime un error y procede con diccionarios vacíos para algunas partes del payload, lo cual podría no ser ideal).
- **Refactorización Potencial**: Si `api_router.py` crece mucho, considerar mover la función `convert_task_orm_to_pydantic` a un módulo de utilidades o helpers.
- **Pruebas de Ejecución de Tareas**: Una vez que los otros MCPs (LinkedIn, X, etc.) estén disponibles, se deben realizar pruebas exhaustivas del proceso de ejecución de tareas por parte del worker de APScheduler, incluyendo la correcta llamada a los MCPs de destino y el manejo de sus respuestas.
- **Variables de Entorno**: Asegurar que todas las configuraciones sensibles (claves de API, URLs de bases de datos, secretos) se gestionen a través de variables de entorno en lugar de estar codificadas directamente.


