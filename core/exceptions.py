class UserFacingError(Exception):
    """
    Excepción controlada para mensajes orientados al usuario final (cliente o maestro).
    Permite enviar un mensaje amigable y un código de error predecible a las aplicaciones móviles y web.
    """
    def __init__(self, user_message: str, code: str = "BAD_REQUEST", status_code: int = 400):
        super().__init__(user_message)
        self.user_message = user_message
        self.code = code
        self.status_code = status_code

    def __str__(self):
        return self.user_message
