"""Demostración del patrón Builder (GoF).

Idea central: construir un objeto complejo (una consulta SQL) paso a paso,
con métodos encadenables que devuelven `self` (fluent interface), y validar
todo una sola vez en `build()`, de modo que el Product nunca exista en un
estado inválido.

Relación con el repo: `CrawlerDispatcher.build().register_linkedin().register_medium()`
usa el encadenamiento fluido propio de este patrón; aquí se añade la pieza que
le falta para ser un Builder canónico: un `build()` que produce un objeto
final inmutable y validado.

Ejecutar:
    poetry run python practica/builder_demo.py
"""

from dataclasses import dataclass

from loguru import logger


# ---------------------------------------------------------------------------
# Product: el objeto complejo que queremos construir (inmutable una vez creado)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ConsultaSQL:
    tabla: str
    columnas: tuple[str, ...]
    filtros: tuple[str, ...] = ()
    orden: str | None = None
    limite: int | None = None

    def to_sql(self) -> str:
        cols = ", ".join(self.columnas)
        sql = f"SELECT {cols} FROM {self.tabla}"
        if self.filtros:
            sql += " WHERE " + " AND ".join(self.filtros)
        if self.orden:
            sql += f" ORDER BY {self.orden}"
        if self.limite is not None:
            sql += f" LIMIT {self.limite}"
        return sql + ";"


# ---------------------------------------------------------------------------
# Builder: acumula las piezas paso a paso y valida todo al final en build()
# ---------------------------------------------------------------------------
class ConsultaBuilder:
    def __init__(self) -> None:
        self._tabla: str | None = None
        self._columnas: list[str] = []
        self._filtros: list[str] = []
        self._orden: str | None = None
        self._limite: int | None = None

    def from_(self, tabla: str) -> "ConsultaBuilder":
        self._tabla = tabla
        return self  # devolver self es lo que permite encadenar llamadas

    def select(self, *columnas: str) -> "ConsultaBuilder":
        self._columnas.extend(columnas)
        return self

    def where(self, filtro: str) -> "ConsultaBuilder":
        self._filtros.append(filtro)
        return self

    def order_by(self, columna: str, descendente: bool = False) -> "ConsultaBuilder":
        self._orden = f"{columna} {'DESC' if descendente else 'ASC'}"
        return self

    def limit(self, n: int) -> "ConsultaBuilder":
        if n <= 0:
            raise ValueError("El límite debe ser positivo")
        self._limite = n
        return self

    def build(self) -> ConsultaSQL:
        """Valida las piezas obligatorias y devuelve el Product terminado."""
        if not self._tabla:
            raise ValueError("Falta la tabla: usa .from_(...)")
        if not self._columnas:
            raise ValueError("Falta al menos una columna: usa .select(...)")
        return ConsultaSQL(
            tabla=self._tabla,
            columnas=tuple(self._columnas),
            filtros=tuple(self._filtros),
            orden=self._orden,
            limite=self._limite,
        )


if __name__ == "__main__":
    # Ejemplo 1: consulta completa, pasos encadenados en cualquier orden
    consulta = (
        ConsultaBuilder()
        .select("id", "titulo", "autor")
        .from_("articulos")
        .where("autor = 'Paul Iusztin'")
        .where("fecha > '2024-01-01'")
        .order_by("fecha", descendente=True)
        .limit(10)
        .build()
    )
    logger.info(f"Consulta completa: {consulta.to_sql()}")

    # Ejemplo 2: consulta mínima; los pasos opcionales simplemente se omiten
    minima = ConsultaBuilder().select("*").from_("usuarios").build()
    logger.info(f"Consulta mínima:   {minima.to_sql()}")

    # Ejemplo 3: build() rechaza un objeto incompleto (nunca existe inválido)
    try:
        ConsultaBuilder().select("id").build()  # falta la tabla
    except ValueError as e:
        logger.warning(f"Error esperado: {e}")
