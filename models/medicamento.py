from typing import Optional

class Medicamento:
    """Sub-entidad dependiente que conforma el cuerpo compuesto de una prescripción."""
    def __init__(self, id_med: Optional[int], receta_id: int, nombre: str, 
                 cantidad: float, indicaciones: str) -> None:
        self._id: Optional[int] = id_med
        self._recetaId: int = receta_id
        self._nombre: str = nombre
        self._cantidad: float = cantidad
        self._indicaciones: str = indicaciones

    @property
    def id(self) -> Optional[int]: return self._id
    @property
    def recetaId(self) -> int: return self._recetaId
    @property
    def nombre(self) -> str: return self._nombre
    @property
    def cantidad(self) -> float: return self._cantidad
    @property
    def indicaciones(self) -> str: return self._indicaciones

    def obtener_descripcion(self) -> str:
        return f"{self._nombre} - {self._cantidad} unidades - {self._indicaciones}"

    def validar(self) -> bool:
        """Validación defensiva de la integridad del medicamento."""
        return bool(self._nombre.strip()) and self._cantidad > 0 and bool(self._indicaciones.strip())

    def __str__(self) -> str:
        return self.obtener_descripcion()