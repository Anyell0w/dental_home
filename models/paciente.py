from datetime import datetime
from typing import Optional


class Paciente:
    """Representa la entidad Paciente y gestiona su ciclo de vida y métricas básicas."""

    def __init__(self, id_paciente: Optional[int], nombre: str, apellido: str, dni: str,
                 telefono: str, sexo: str, fecha_nacimiento: str, direccion: str,
                 estado: bool = True, registrado_por: Optional[int] = None) -> None:
        self._id: Optional[int] = id_paciente
        self._nombre: str = nombre
        self._apellido: str = apellido
        self._dni: str = dni
        self._telefono: str = telefono
        self._sexo: str = sexo
        self._fechaNacimiento: str = fecha_nacimiento  # Formato DD/MM/AAAA
        self._direccion: str = direccion
        self._estado: bool = estado
        self._registradoPor: Optional[int] = registrado_por

    # ------------------------------------------------------------------
    # Propiedades de solo lectura
    # ------------------------------------------------------------------
    @property
    def id(self) -> Optional[int]:
        return self._id

    @property
    def dni(self) -> str:
        return self._dni

    @dni.setter
    def dni(self, valor: str) -> None:
        # Validación opcional
        if not valor or not valor.strip():
            raise ValueError("El DNI no puede estar vacío.")

        valor = valor.strip()

        if not valor.isdigit():
            raise ValueError("El DNI solo debe contener números.")

        if len(valor) != 8:
            raise ValueError("El DNI debe tener 8 dígitos.")

        self._dni = valor

    @property
    def estado(self) -> bool:
        return self._estado

    @property
    def registrado_por(self) -> Optional[int]:
        return self._registradoPor

    # ------------------------------------------------------------------
    # Propiedades con getter y setter (encapsulamiento real)
    # ------------------------------------------------------------------
    @property
    def nombre(self) -> str:
        return self._nombre

    @nombre.setter
    def nombre(self, valor: str) -> None:
        if not valor or not valor.strip():
            raise ValueError("El nombre no puede estar vacío.")
        self._nombre = valor.strip()

    @property
    def apellido(self) -> str:
        return self._apellido

    @apellido.setter
    def apellido(self, valor: str) -> None:
        if not valor or not valor.strip():
            raise ValueError("El apellido no puede estar vacío.")
        self._apellido = valor.strip()

    @property
    def telefono(self) -> str:
        return self._telefono

    @telefono.setter
    def telefono(self, valor: str) -> None:
        self._telefono = valor.strip() if valor else ""

    @property
    def direccion(self) -> str:
        return self._direccion

    @direccion.setter
    def direccion(self, valor: str) -> None:
        self._direccion = valor.strip() if valor else ""

    @property
    def sexo(self) -> str:
        return self._sexo

    @sexo.setter
    def sexo(self, valor: str) -> None:
        valor = (valor or "").strip().upper()
        if valor not in ("M", "F"):
            raise ValueError("El sexo debe ser 'M' o 'F'.")
        self._sexo = valor

    @property
    def fecha_nacimiento(self) -> str:
        return self._fechaNacimiento

    @fecha_nacimiento.setter
    def fecha_nacimiento(self, valor: str) -> None:
        # La app opera con fechas en formato DD/MM/AAAA (igual que el formulario
        # y que calcular_edad). Lanza ValueError si el formato es inválido.
        datetime.strptime(valor, "%d/%m/%Y")
        self._fechaNacimiento = valor

    # ------------------------------------------------------------------
    # Comportamiento
    # ------------------------------------------------------------------
    def obtener_nombre_completo(self) -> str:
        return f"{self._nombre} {self._apellido}"

    def calcular_edad(self) -> int:
        """Determina la edad cronológica exacta basada en la fecha actual.

        Lanza ValueError si la fecha de nacimiento almacenada no tiene un
        formato válido, en vez de ocultar el problema devolviendo 0.
        """
        fecha_nac = datetime.strptime(self._fechaNacimiento, "%d/%m/%Y")
        hoy = datetime.now()
        return hoy.year - fecha_nac.year - ((hoy.month, hoy.day) < (fecha_nac.month, fecha_nac.day))

    def dar_de_baja(self) -> None:
        self._estado = False

    def activar(self) -> None:
        self._estado = True

    # ------------------------------------------------------------------
    # Igualdad e identidad de negocio
    # ------------------------------------------------------------------
    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Paciente):
            return NotImplemented
        # Dos pacientes son el mismo registro si comparten ID (cuando ambos
        # están persistidos) o, en su defecto, el mismo DNI.
        if self._id is not None and other._id is not None:
            return self._id == other._id
        return self._dni == other._dni

    def __hash__(self) -> int:
        return hash(self._id) if self._id is not None else hash(self._dni)

    def __str__(self) -> str:
        return f"Paciente('{self.obtener_nombre_completo()}', DNI='{self._dni}')"