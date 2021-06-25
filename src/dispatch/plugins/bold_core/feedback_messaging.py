from dispatch.messaging.strings import LEARNED_LESSON_NOTIFICATION, INCIDENT_TITLE_ES, MessageType
from dispatch.plugins.dispatch_slack.plugin import SlackConversationPlugin

plugin = SlackConversationPlugin()

notification_kwargs = [
    {
        "name": "INC-009",
        "title": "Fallo en la confirmación del comercio",
        "lessons": "* Compartir de manera mas eficiente la información acerca de los errores que se han identificado, "
                   "así se pueden detectar comportamientos con anterioridad y se evitan incidentes."
    },
    {
        "name": "Inc-010",
        "title": "Reporte de múltiples errores en generación de transacciones",
        "lessons": "* No subir cambios de actualizaciones de comercios en horas transaccionales.\n"
                   "* Validar y pre validar en los diseños si es necesario replicar información a las otras cuentas.\n"
                   "* Validar cuando un PR puede afectar a mas de una cuenta cuando se realizan ajustes en batch."
    },
    {
        "name": "INC-012",
        "title": "Error en lambda que ejecuta las reversiones",
        "lessons": "* Regresiones por parte del equipo de Calidad (no sólo probar flujos básicos sino tener en cuenta "
                   "flujos alternos y/o casos especiales).\n"
                   "* Los DEV (back, front, app) antiguos tener presente y "
                   "validar qué se puede ver afectado con las nuevas implementaciones, sobre todo con Dev nuevos y "
                   "que no conocen mucho funcionalidades antiguas y/o reglas de negocio.\n"
                   "* Tener en cuenta si la "
                   "implementación que se esta realizando puede afectar funcionalidades de otro tipo (por ej: que se "
                   "este trabajando fingerprint para pagos POS y LINK pero se dañe historial o movimientos).\n"
                   "* Se deben mejorar los logs para incluir la información completa de la TX generada."
    },
    {
        "name": "INC-013",
        "title": "Error en e-commerce con los datos de envío del datáfono",
        "lessons": "* Habían unas reglas de retrocompatibilidad en backend pero ya no eran necesarias en ese momento.\n"
                   "* No reflexionamos sobre la necesidad de esas reglas y por eso se requerían mas cosas de las que en "
                   "realidad se necesitaban. Siempre deberíamos preguntarnos si estamos usando lo mínimo para "
                   "funcionar y así evitar validaciones que no aportan."
    },
    {
        "name": "INC-015",
        "title": "Se detiene generación de movs",
        "lessons": "* Comunicación precisa entre los equipos (PM) acerca de los nuevos features que saldrán, de manera "
                   "que no afectemos otras funcionalidades.\n"
                   "* Tener en cuenta utilizar RemoteConfig para nuevas "
                   "implementaciones que puedan generar afectaciones en los comercios (payouts, nuevos bines, "
                   "etc).\n"
                   "* Considerar en qué features se pueda tener una opción genérica/default. (por ej: en caso "
                   "de nuevos bines que no se soporten en back, dejar una configuración por defecto para que no se "
                   "rechacen o aprueben incorrectamente TX). "
    },
    {
        "name": "INC-014",
        "title": "No se realiza la actualización de datáfonos",
        "lessons": "* Se debio revisar la app en qa para evitar errores, comprobando el correcto funcionamiento del"
        "datafono y de los flujos que intervienen (actualización, vinculación, transacción).\n"
        "* Cuando el dev modifique una funcionalidad anterior, se debe verificar que no se afecte.\n"
        "* Apreder cuando se debe realizar rollback"
        "directamente al encontrar el error en produccion, y no realizar pequeñas correcciones que pueden no"
        "funcionar.\n"
        "* Si se reliza un ajuste para corregir un error en producción se debe siempre realizar pruebas"
        "antes de subir el cambio.\n"
        "* Revisar el proceso de rollback y de atención a incidentes y capacitar a nuevos"
        "Devs en pasos a seguir una vez ocurra un incidente en producción. \n"
        "* Mientras se soluciones la saturación en"
        "soporte, se debe continuar con la revisión de los incidentes. en el canal de soporte/tech"
    },
    {
        "name": "INC-017",
        "title": "Reportes en JetAdmin no estan funcionando",
        "lessons":
            "* Las herramientas se deben utilizar para lo que fueron"
            "diseñadas. Jet admin es más una interfaz operativa que una herramienta de BI.\n"
            "* La BBDD relacional"
            "normalizada es adecuada para el almacenamiento de datos, pero no tiene el mejor rendimiento al momento de"
            "hacer queries complejas.\n"
            "* No todos los usuarios necesitan realmente acceso, se podría reconsiderar"
            "algunos para así disminuir concurrencia y evitar posible fallos, además de ahorrar costos."
    },
    {
        "name": "INC-019",
        "title": "Falla en la maquina de estados al realizar send to bank",
        "lessons": "* En máquinas de estados con una alta concurrencia (más de 500 ejecuciones corriendo de manera "
                   "simultanea) es necesario utilizar integración de Lambdas a través de SQS.\n"
                   "* Una alternativa adicional para evitar fallos con el throttling en escenarios de una alta "
                   "concurrencia de ejecuciones activas en las máquinas de estados puede ser la implementación de "
                   "reintentos con back-off para la excepción 429 de aws Lambdas (Too many requests). "
                   "https://docs.aws.amazon.com/step-functions/latest/dg/concepts-error-handling.html "
    }
]

template = LEARNED_LESSON_NOTIFICATION.copy()
template.insert(1, INCIDENT_TITLE_ES)

for kwargs in notification_kwargs:
    plugin.send(
        "C025WQ7E8MP",  # Test
        # "C0260U01NT0", - PRO
        "Incident Notification",
        template,
        notification_type=MessageType.incident_notification,
        persist=False,
        **kwargs
    )
