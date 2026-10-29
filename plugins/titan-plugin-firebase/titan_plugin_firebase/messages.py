"""User-facing text owned by the Firebase plugin."""


class Messages:
    """Firebase messages grouped by workflow surface."""

    class Inventory:
        """Multi-project Remote Config inventory messages."""

        STEP_TITLE = "Inventariar claves y valores"
        PLUGIN_UNAVAILABLE = "El plugin de Firebase no esta disponible"
        TARGETS_REQUIRED = (
            "Faltan los proyectos. Ejecuta firebase_select_targets antes de este paso."
        )
        READING_PROJECT = "Leyendo {project_id}..."
        UNEXPECTED_RESPONSE = "Respuesta inesperada al leer Remote Config"
        NO_READABLE_PROJECTS = "No se pudo leer ningun proyecto de Firebase."
        PROJECT_READ_FAILURES = "{count} proyecto(s) no se pudieron leer."
        READ_STATUS_HEADERS = ("Marca", "Claves", "Condiciones", "Estado")
        READ_STATUS_TITLE = "Estado de lectura"
        VALUE_VIEW = "Vista de valores: {label}"
        CONFIGURED_VALUE_VIEWS = "Vistas de valores configuradas: {groups}."
        SUMMARY = (
            "{readable}/{selected} proyectos leidos · {unique} claves unicas · "
            "{common} comunes · {conflicts} {conflict_label} de tipo"
        )
        TYPE_CONFLICT = "conflicto"
        TYPE_CONFLICT_PLURAL = "conflictos"
        KEYS_AND_VALUES = "Claves y valores"
        NO_VALUES_IN_VIEW = (
            "No hay valores para la vista de condiciones seleccionada."
        )
        NO_KEYS = "Los proyectos leidos no tienen claves."
        TYPE_CONFLICT_WARNING = "{count} clave(s) tienen conflictos de tipo."
        BULK_SUMMARY = (
            "{safe} clave(s) aptas para bulk; "
            "{blocked} requieren revisión por proyecto."
        )
        UNKNOWN_TYPE_WARNING = "{count} clave(s) tienen tipo efectivo UNKNOWN."
        SUCCESS = (
            "{unique} claves unicas; "
            "{common} comunes en {projects} proyectos"
        )
        VALUE_HEADERS = (
            "Marca",
            "Entorno",
            "Condicion",
            "Valor",
            "Origen",
            "Editable",
        )
        STATUS_ERROR = "error: {error}"
        STATUS_OK = "ok"
        VALUE_UNREAD = "No leido"
        VALUE_MISSING = "No existe"
        VALUE_NOT_IN_VIEW = "Sin valores en esta vista"
        EDITABLE_YES = "si"
        EDITABLE_NO = "no"
        STATUS_TYPE_CONFLICT = "conflicto de tipo"
        STATUS_MIXED_VALUES = "valores mixtos"
        STATUS_NOT_EDITABLE = "no editable"
        STATUS_UNKNOWN_TYPE = "tipo desconocido"
        STATUS_MISSING = "falta en {count}"
        STATUS_UNREAD = "{count} sin leer"
        DESCRIPTIONS_DIFFER = "Descripciones distintas por marca:"

    class Targets:
        """Configured-project selection messages."""

        SUMMARY_HEADERS = ("Marca", "Entornos", "Grupo")


msg = Messages()
